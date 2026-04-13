from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from temporalio.client import WithStartWorkflowOperation
from temporalio.common import WorkflowIDConflictPolicy

from app.services.borrower_case import FileBorrowerCaseService
from app.orchestrator.client import get_temporal_client
from app.orchestrator.models import CollectionsWorkflowInput, CollectionsWorkflowState
from app.orchestrator.workflows import BorrowerCollectionsWorkflow


class WorkflowMessageRequest(BaseModel):
    borrower_id: str
    workflow_id: str | None = None
    message: str


class WorkflowMessageResponse(BaseModel):
    workflow_id: str
    reply: str | None = None
    stage: str
    final_result: str | None = None


router = APIRouter(prefix="/workflows", tags=["workflows"])
borrower_case_service = FileBorrowerCaseService()


@router.post("/messages", response_model=WorkflowMessageResponse)
async def submit_borrower_message(payload: WorkflowMessageRequest) -> WorkflowMessageResponse:
    borrower_case = borrower_case_service.get_borrower_case(payload.borrower_id)
    if borrower_case is None:
        raise HTTPException(status_code=404, detail="Borrower case not found")

    workflow_id = payload.workflow_id or borrower_case.workflow_id
    client = await get_temporal_client()

    try:
        state = await client.execute_update_with_start_workflow(
            BorrowerCollectionsWorkflow.handle_borrower_message,
            payload.message,
            start_workflow_operation=WithStartWorkflowOperation(
                BorrowerCollectionsWorkflow.run,
                CollectionsWorkflowInput(
                    borrower_id=payload.borrower_id,
                    workflow_id=workflow_id,
                ),
                id=workflow_id,
                task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "collections-task-queue"),
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
            ),
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return WorkflowMessageResponse(
        workflow_id=workflow_id,
        reply=state.last_agent_reply,
        stage=state.borrower_case.stage.value,
        final_result=state.final_result,
    )


# @router.get("/{workflow_id}", response_model=CollectionsWorkflowState)
# async def get_workflow_state(workflow_id: str) -> CollectionsWorkflowState:
#     client = await get_temporal_client()
#     handle = client.get_workflow_handle(workflow_id)
#     try:
#         state = await handle.query(BorrowerCollectionsWorkflow.get_state)
#     except Exception as error:
#         raise HTTPException(status_code=500, detail=str(error)) from error
#     if state is None:
#         raise HTTPException(status_code=404, detail="Workflow state not found")
#     return state
