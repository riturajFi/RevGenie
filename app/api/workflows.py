from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.borrower_case import FileBorrowerCaseService
from app.temporal.client import get_temporal_client
from app.temporal.models import CollectionsWorkflowInput, CollectionsWorkflowState
from app.temporal.workflows import BorrowerCollectionsWorkflow


class StartWorkflowRequest(BaseModel):
    borrower_id: str
    workflow_id: str | None = None
    response_timeout_seconds: int = 60


class StartWorkflowResponse(BaseModel):
    workflow_id: str


class BorrowerMessageRequest(BaseModel):
    message: str


class BorrowerMessageResponse(BaseModel):
    sent: bool


router = APIRouter(prefix="/workflows", tags=["workflows"])
borrower_case_service = FileBorrowerCaseService()


@router.post("/start", response_model=StartWorkflowResponse)
async def start_workflow(payload: StartWorkflowRequest) -> StartWorkflowResponse:
    borrower_case = borrower_case_service.get_borrower_case(payload.borrower_id)
    if borrower_case is None:
        raise HTTPException(status_code=404, detail="Borrower case not found")

    workflow_id = payload.workflow_id or borrower_case.workflow_id
    client = await get_temporal_client()
    try:
        await client.start_workflow(
            BorrowerCollectionsWorkflow.run,
            CollectionsWorkflowInput(
                borrower_id=payload.borrower_id,
                workflow_id=workflow_id,
                response_timeout_seconds=payload.response_timeout_seconds,
            ),
            id=workflow_id,
            task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "collections-task-queue"),
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return StartWorkflowResponse(workflow_id=workflow_id)


@router.post("/{workflow_id}/messages", response_model=BorrowerMessageResponse)
async def submit_borrower_message(workflow_id: str, payload: BorrowerMessageRequest) -> BorrowerMessageResponse:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    try:
        await handle.signal(BorrowerCollectionsWorkflow.submit_borrower_message, payload.message)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return BorrowerMessageResponse(sent=True)


@router.get("/{workflow_id}", response_model=CollectionsWorkflowState)
async def get_workflow_state(workflow_id: str) -> CollectionsWorkflowState:
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    try:
        state = await handle.query(BorrowerCollectionsWorkflow.get_state)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow state not found")
    return state
