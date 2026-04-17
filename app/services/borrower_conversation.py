from __future__ import annotations

import os
from typing import Any

from temporalio.client import WithStartWorkflowOperation
from temporalio.common import WorkflowIDConflictPolicy

from app.domain.borrower_case import BorrowerCase, CaseStatus, ResolutionMode, Stage
from app.orchestrator.client import get_temporal_client
from app.orchestrator.models import (
    BorrowerMessageWorkflowInput,
    CollectionsWorkflowInput,
    CollectionsWorkflowState,
    ResolutionVoiceCallCompletedInput,
)
from app.orchestrator.workflows import BorrowerCollectionsWorkflow
from app.realtime.models import BorrowerConversationMessage, BorrowerConversationState
from app.services.borrower_case import FileBorrowerCaseService
from app.services.chat_message import get_chat_message_service


class BorrowerConversationService:
    def __init__(self) -> None:
        self.borrower_case_service = FileBorrowerCaseService()
        self.chat_message_service = get_chat_message_service()

    def get_borrower_case(self, borrower_id: str) -> BorrowerCase:
        borrower_case = self.borrower_case_service.get_borrower_case(borrower_id)
        if borrower_case is None:
            raise ValueError(f"Borrower case not found for {borrower_id}")
        return borrower_case

    async def submit_borrower_message(
        self,
        *,
        borrower_id: str,
        message: str,
        default_resolution_mode: ResolutionMode,
        workflow_id: str | None = None,
        resolution_mode: ResolutionMode | None = None,
    ) -> CollectionsWorkflowState:
        borrower_case = self.get_borrower_case(borrower_id)
        if not self._input_enabled(borrower_case):
            raise ValueError("Borrower messaging is currently unavailable for this case state")
        target_workflow_id = workflow_id or borrower_case.workflow_id
        resolved_mode = resolution_mode or default_resolution_mode

        client = await get_temporal_client()
        return await client.execute_update_with_start_workflow(
            BorrowerCollectionsWorkflow.handle_borrower_message,
            BorrowerMessageWorkflowInput(
                message=message,
                resolution_mode=resolved_mode,
            ),
            start_workflow_operation=WithStartWorkflowOperation(
                BorrowerCollectionsWorkflow.run,
                CollectionsWorkflowInput(
                    borrower_id=borrower_id,
                    workflow_id=target_workflow_id,
                    resolution_mode=resolved_mode,
                ),
                id=target_workflow_id,
                task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "collections-task-queue"),
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            ),
        )

    def can_accept_borrower_message(self, borrower_id: str) -> bool:
        return self._input_enabled(self.get_borrower_case(borrower_id))

    def resolve_workflow_id_for_call(self, call: dict[str, Any]) -> str | None:
        metadata = call.get("metadata")
        if isinstance(metadata, dict):
            workflow_id = metadata.get("workflow_id")
            if isinstance(workflow_id, str) and workflow_id.strip():
                return workflow_id.strip()

            borrower_id = metadata.get("borrower_id")
            if isinstance(borrower_id, str) and borrower_id.strip():
                borrower_case = self.borrower_case_service.get_borrower_case(borrower_id.strip())
                if borrower_case is not None:
                    return borrower_case.workflow_id

        incoming_call_id = str(call.get("call_id") or "").strip()
        if not incoming_call_id:
            return None

        for borrower_case in self.borrower_case_service.list_borrower_cases():
            if borrower_case.resolution_call_id == incoming_call_id:
                return borrower_case.workflow_id
        return None

    async def submit_resolution_call_completion(self, call: dict[str, Any]) -> CollectionsWorkflowState | None:
        workflow_id = self.resolve_workflow_id_for_call(call)
        if not workflow_id:
            return None

        client = await get_temporal_client()
        handle = client.get_workflow_handle(workflow_id)
        return await handle.execute_update(
            BorrowerCollectionsWorkflow.handle_resolution_call_completed,
            ResolutionVoiceCallCompletedInput(call=call),
        )

    def build_conversation_state(
        self,
        borrower_id: str,
        *,
        workflow_state: CollectionsWorkflowState | None = None,
    ) -> BorrowerConversationState:
        borrower_case = workflow_state.borrower_case if workflow_state is not None else self.get_borrower_case(borrower_id)
        workflow_id = borrower_case.workflow_id
        final_result = workflow_state.final_result if workflow_state is not None else borrower_case.final_disposition
        messages = self.chat_message_service.list_visible_workflow_messages(borrower_id, workflow_id)

        return BorrowerConversationState(
            borrower_case=borrower_case,
            workflow_id=workflow_id,
            final_result=final_result,
            input_enabled=self._input_enabled(borrower_case),
            messages=[
                BorrowerConversationMessage(
                    id=f"{index}_{item.agent_id}_{item.created_at.isoformat()}",
                    actor=self._actor(item.sender_type),
                    text=item.message,
                    created_at=item.created_at,
                )
                for index, item in enumerate(messages)
            ],
        )

    def _input_enabled(self, borrower_case: BorrowerCase) -> bool:
        if borrower_case.case_status != CaseStatus.OPEN:
            return False
        if borrower_case.final_disposition:
            return False
        if borrower_case.stage == Stage.RESOLUTION and borrower_case.resolution_mode == ResolutionMode.VOICE:
            return False
        return True

    def _actor(self, sender_type: str) -> str:
        if sender_type == "agent":
            return "agent"
        if sender_type == "borrower":
            return "borrower"
        return "system"


borrower_conversation_service = BorrowerConversationService()
