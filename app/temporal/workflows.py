from __future__ import annotations

import asyncio
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
        send_assessment_prompt,
        send_final_notice_prompt,
        send_resolution_prompt,
    )
    from app.temporal.models import (
        AgentPromptActivityInput,
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
        borrower_case = await self._activity(
            load_borrower_case,
            input.borrower_id,
        )
        borrower_case.workflow_id = input.workflow_id
        borrower_case.stage = Stage.ASSESSMENT
        borrower_case.case_status = CaseStatus.OPEN
        borrower_case = await self._activity(save_borrower_case, borrower_case)

        self.state = CollectionsWorkflowState(
            borrower_case=borrower_case,
            assessment_no_response_attempts=0,
            last_agent_reply=None,
            final_result=None,
            pending_messages=[],
        )

        await self._start_assessment_stage()
        await self._run_assessment_stage(input.response_timeout_seconds)

        if self.state.final_result is not None:
            return self.state

        await self._start_resolution_stage()
        await self._run_resolution_stage()

        if self.state.final_result is not None:
            return self.state

        await self._start_final_notice_stage()
        await self._run_final_notice_stage()
        return self.state

    @workflow.signal
    def submit_borrower_message(self, message: str) -> None:
        assert self.state is not None
        self.state.pending_messages.append(message)

    @workflow.query
    def get_state(self) -> CollectionsWorkflowState | None:
        return self.state

    async def _run_assessment_stage(self, timeout_seconds: int) -> None:
        assert self.state is not None
        while self.state.borrower_case.stage == Stage.ASSESSMENT:
            message = await self._next_message(timeout_seconds)
            if message is None:
                self.state.assessment_no_response_attempts += 1
                if self.state.assessment_no_response_attempts >= 3:
                    await self._transition_to_stage(Stage.RESOLUTION)
                    return
                prompt_reply = await self._activity(
                    send_assessment_prompt,
                    AgentPromptActivityInput(
                        borrower_case=self.state.borrower_case,
                        instruction=(
                            f"No borrower response received. Send a concise assessment follow-up. "
                            f"This is retry {self.state.assessment_no_response_attempts} of 3."
                        ),
                    ),
                )
                self.state.last_agent_reply = prompt_reply
                continue

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
                await self._transition_to_stage(Stage.RESOLUTION)
                return

    async def _run_resolution_stage(self) -> None:
        assert self.state is not None
        while self.state.borrower_case.stage == Stage.RESOLUTION:
            message = await self._next_message()
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
                return
            if turn_result.stage_result.stage_outcome == AgentStageOutcome.NO_DEAL:
                await self._transition_to_stage(Stage.FINAL_NOTICE)
                return

    async def _run_final_notice_stage(self) -> None:
        assert self.state is not None
        while self.state.borrower_case.stage == Stage.FINAL_NOTICE:
            message = await self._next_message()
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
                return
            if turn_result.stage_result.stage_outcome == AgentStageOutcome.NO_RESOLUTION:
                await self._complete_workflow("FLAG_FOR_LEGAL_WRITE_OFF", CaseStatus.CLOSED)
                return

    async def _start_assessment_stage(self) -> None:
        assert self.state is not None
        prompt_reply = await self._activity(
            send_assessment_prompt,
            AgentPromptActivityInput(
                borrower_case=self.state.borrower_case,
                instruction=(
                    "Start the assessment stage. Ask for identity verification using partial account information "
                    "and ask for the borrower's current financial situation."
                ),
            ),
        )
        self.state.last_agent_reply = prompt_reply

    async def _start_resolution_stage(self) -> None:
        assert self.state is not None
        prompt_reply = await self._activity(
            send_resolution_prompt,
            AgentPromptActivityInput(
                borrower_case=self.state.borrower_case,
                instruction=(
                    "Start the resolution stage. Present policy-bound options, state any relevant deadline, "
                    "and continue from the assessment handoff summary without re-verifying identity."
                ),
            ),
        )
        self.state.last_agent_reply = prompt_reply

    async def _start_final_notice_stage(self) -> None:
        assert self.state is not None
        prompt_reply = await self._activity(
            send_final_notice_prompt,
            AgentPromptActivityInput(
                borrower_case=self.state.borrower_case,
                instruction=(
                    "Start the final notice stage. State the final available option if any, the hard expiry, "
                    "and the exact next consequence if there is no resolution."
                ),
            ),
        )
        self.state.last_agent_reply = prompt_reply

    async def _next_message(self, timeout_seconds: int | None = None) -> str | None:
        assert self.state is not None
        if timeout_seconds is None:
            await workflow.wait_condition(lambda: len(self.state.pending_messages) > 0)
            return self.state.pending_messages.pop(0)
        try:
            await workflow.wait_condition(
                lambda: len(self.state.pending_messages) > 0,
                timeout=timedelta(seconds=timeout_seconds),
            )
        except asyncio.TimeoutError:
            return None
        return self.state.pending_messages.pop(0)

    async def _transition_to_stage(self, stage: Stage) -> None:
        assert self.state is not None
        self.state.borrower_case.stage = stage
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
