from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.domain.borrower_case import AgentStageOutcome, CaseStatus, ResolutionMode, Stage
    from app.orchestrator.activities import (
        finalize_resolution_call,
        load_borrower_case,
        run_assessment_turn,
        run_final_notice_turn,
        run_resolution_turn,
        save_borrower_case,
        start_final_notice_stage,
        start_resolution_call,
    )
    from app.orchestrator.models import (
        AgentTurnActivityInput,
        BorrowerMessageWorkflowInput,
        CollectionsWorkflowInput,
        CollectionsWorkflowState,
        ResolutionCallActivityInput,
        ResolutionVoiceCallCompletedInput,
    )
    from app.services.workflow_channel import workflow_channel_service


@workflow.defn
class BorrowerCollectionsWorkflow:
    @workflow.init
    def __init__(self, input: CollectionsWorkflowInput) -> None:
        self.input = input
        self.state: CollectionsWorkflowState | None = None

    @workflow.run
    async def run(self, input: CollectionsWorkflowInput) -> CollectionsWorkflowState:
        await self._ensure_state(input)

        await workflow.wait_condition(
            lambda: self.state is not None
            and self.state.final_result is not None
            and workflow.all_handlers_finished()
        )
        return self.state

    @workflow.update
    async def handle_borrower_message(self, input: BorrowerMessageWorkflowInput) -> CollectionsWorkflowState:

        # TODO: Do we need this?
        if self.state is None:
            await self._ensure_state(self.input)

        assert self.state is not None
        self.state.borrower_case.simulation_uniqueness_tag = input.simulation_uniqueness_tag
        self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)

        # VOICE for interactive and chat for training
        await self._apply_resolution_mode(input.resolution_mode)

        if self.state.borrower_case.stage == Stage.ASSESSMENT:
            turn_result = await self._activity(
                run_assessment_turn,
                AgentTurnActivityInput(
                    borrower_case=self.state.borrower_case,
                    message=input.message,
                ),
            )
            self.state.borrower_case = turn_result.borrower_case
            self.state.last_agent_reply = turn_result.stage_result.reply
            self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)
            if turn_result.stage_result.stage_outcome == AgentStageOutcome.ASSESSMENT_COMPLETE:
                self.state.borrower_case.stage = Stage.RESOLUTION
                self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)
                if self.state.borrower_case.resolution_mode == ResolutionMode.VOICE:
                    await self._ensure_resolution_voice_call_started()
            return self.state

        if self.state.borrower_case.stage == Stage.RESOLUTION:
            if self.state.borrower_case.resolution_mode == ResolutionMode.VOICE:
                await self._ensure_resolution_voice_call_started()
                self.state.last_agent_reply = None
                return self.state
            turn_result = await self._activity(
                run_resolution_turn,
                AgentTurnActivityInput(
                    borrower_case=self.state.borrower_case,
                    message=input.message,
                ),
            )
            self.state.borrower_case = turn_result.borrower_case
            self.state.last_agent_reply = turn_result.stage_result.reply
            self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)
            if turn_result.stage_result.stage_outcome == AgentStageOutcome.DEAL_AGREED:
                await self._complete_workflow("AGREEMENT_LOGGED", CaseStatus.RESOLVED)
            elif turn_result.stage_result.stage_outcome == AgentStageOutcome.NO_DEAL:
                self.state.borrower_case.stage = Stage.FINAL_NOTICE
                self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)
            return self.state

        turn_result = await self._activity(
            run_final_notice_turn,
            AgentTurnActivityInput(
                borrower_case=self.state.borrower_case,
                message=input.message,
            ),
        )
        self.state.borrower_case = turn_result.borrower_case
        self.state.last_agent_reply = turn_result.stage_result.reply
        self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)
        if turn_result.stage_result.stage_outcome == AgentStageOutcome.RESOLVED:
            await self._complete_workflow("RESOLUTION_LOGGED", CaseStatus.RESOLVED)
        elif turn_result.stage_result.stage_outcome == AgentStageOutcome.NO_RESOLUTION:
            await self._complete_workflow("FLAG_FOR_LEGAL_WRITE_OFF", CaseStatus.CLOSED)
        return self.state

    @workflow.query
    def get_state(self) -> CollectionsWorkflowState | None:
        return self.state

    @workflow.update
    async def handle_resolution_call_completed(
        self,
        input: ResolutionVoiceCallCompletedInput,
    ) -> CollectionsWorkflowState:
        if self.state is None:
            await self._ensure_state(self.input)

        assert self.state is not None
        if self.state.borrower_case.stage != Stage.RESOLUTION:
            return self.state
        if self.state.borrower_case.resolution_mode != ResolutionMode.VOICE:
            return self.state

        incoming_call_id = str(input.call.get("call_id") or "")
        existing_call_id = self.state.borrower_case.resolution_call_id or ""
        if incoming_call_id and existing_call_id and incoming_call_id != existing_call_id:
            return self.state

        turn_result = await self._activity(
            finalize_resolution_call,
            ResolutionCallActivityInput(
                borrower_case=self.state.borrower_case,
                call=input.call,
            ),
        )
        self.state.borrower_case = turn_result.borrower_case
        self.state.last_agent_reply = turn_result.stage_result.reply
        self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)
        if turn_result.stage_result.stage_outcome == AgentStageOutcome.DEAL_AGREED:
            await self._complete_workflow("AGREEMENT_LOGGED", CaseStatus.RESOLVED)
        elif turn_result.stage_result.stage_outcome == AgentStageOutcome.NO_DEAL:
            self.state.borrower_case.stage = Stage.FINAL_NOTICE
            self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)
            final_notice_result = await self._activity(start_final_notice_stage, self.state.borrower_case)
            self.state.borrower_case = final_notice_result.borrower_case
            self.state.last_agent_reply = final_notice_result.stage_result.reply
            self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)
        return self.state

    async def _ensure_state(self, input: CollectionsWorkflowInput) -> None:
        if self.state is not None:
            return
        borrower_case = await self._activity(load_borrower_case, input.borrower_id)
        borrower_case.workflow_id = input.workflow_id
        borrower_case.case_status = CaseStatus.OPEN
        borrower_case.final_disposition = None
        borrower_case.resolution_mode = input.resolution_mode
        borrower_case.prompt_version_overrides = input.prompt_version_overrides
        borrower_case.simulation_uniqueness_tag = input.simulation_uniqueness_tag
        borrower_case = await self._activity(save_borrower_case, borrower_case)
        self.state = CollectionsWorkflowState(
            borrower_case=borrower_case,
            last_agent_reply=None,
            final_result=None,
        )

    async def _apply_resolution_mode(self, requested_mode: ResolutionMode | None) -> None:
        assert self.state is not None
        resolved_mode = workflow_channel_service.resolve_resolution_mode(
            requested_mode,
            borrower_case=self.state.borrower_case,
            default_mode=self.input.resolution_mode,
        )
        if not workflow_channel_service.update_resolution_mode(self.state.borrower_case, resolved_mode):
            return
        self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)

    async def _ensure_resolution_voice_call_started(self) -> None:
        assert self.state is not None
        if self.state.borrower_case.resolution_mode != ResolutionMode.VOICE:
            return
        if self.state.borrower_case.resolution_call_id and self.state.borrower_case.resolution_call_status in {
            "registered",
            "ongoing",
            "ended",
        }:
            return
        call_result = await self._activity(start_resolution_call, self.state.borrower_case)
        self.state.borrower_case.resolution_call_id = call_result.call_id
        self.state.borrower_case.resolution_call_status = call_result.call_status or "registered"
        self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)

    async def _complete_workflow(self, result: str, case_status: CaseStatus) -> None:
        assert self.state is not None
        self.state.final_result = result
        self.state.borrower_case.final_disposition = result
        self.state.borrower_case.case_status = case_status
        self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)

    async def _activity(self, fn, arg):
        return await workflow.execute_activity(
            fn,
            arg,
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
