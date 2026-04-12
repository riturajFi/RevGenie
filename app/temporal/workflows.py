from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.domain.borrower_case import AgentStageOutcome, CaseStatus, Stage
    from app.temporal.activities import (
        load_borrower_case,
        run_assessment_turn,
        run_final_notice_turn,
        run_resolution_turn,
        save_borrower_case,
    )
    from app.temporal.models import (
        AgentTurnActivityInput,
        CollectionsWorkflowInput,
        CollectionsWorkflowState,
    )


@workflow.defn
class BorrowerCollectionsWorkflow:
    def __init__(self) -> None:
        self.state: CollectionsWorkflowState | None = None

    @workflow.run
    async def run(self, input: CollectionsWorkflowInput) -> CollectionsWorkflowState:
        borrower_case = await self._activity(load_borrower_case, input.borrower_id)
        borrower_case.workflow_id = input.workflow_id
        borrower_case.case_status = CaseStatus.OPEN
        borrower_case.final_disposition = None
        borrower_case = await self._activity(save_borrower_case, borrower_case)

        self.state = CollectionsWorkflowState(
            borrower_case=borrower_case,
            last_agent_reply=None,
            final_result=None,
        )

        await workflow.wait_condition(lambda: self.state is not None and self.state.final_result is not None)
        return self.state

    @workflow.update
    async def handle_borrower_message(self, message: str) -> CollectionsWorkflowState:
        assert self.state is not None

        if self.state.borrower_case.stage == Stage.ASSESSMENT:
            turn_result = await self._activity(
                run_assessment_turn,
                AgentTurnActivityInput(
                    borrower_case=self.state.borrower_case,
                    message=message,
                ),
            )
            self.state.borrower_case = turn_result.borrower_case
            self.state.last_agent_reply = turn_result.stage_result.reply
            self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)
            if turn_result.stage_result.stage_outcome == AgentStageOutcome.ASSESSMENT_COMPLETE:
                self.state.borrower_case.stage = Stage.RESOLUTION
                self.state.borrower_case = await self._activity(save_borrower_case, self.state.borrower_case)
            return self.state

        if self.state.borrower_case.stage == Stage.RESOLUTION:
            turn_result = await self._activity(
                run_resolution_turn,
                AgentTurnActivityInput(
                    borrower_case=self.state.borrower_case,
                    message=message,
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
                message=message,
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
