from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.domain.borrower_case import ResolutionMode
from app.services.borrower_conversation import borrower_conversation_service
from app.services.workflow_channel import DEFAULT_BORROWER_RESOLUTION_MODE, DEFAULT_TESTER_RESOLUTION_MODE


class WorkflowMessageRequest(BaseModel):
    borrower_id: str
    workflow_id: str | None = None
    message: str
    resolution_mode: ResolutionMode | None = None
    prompt_version_overrides: dict[str, str] | None = None


class WorkflowMessageResponse(BaseModel):
    workflow_id: str
    reply: str | None = None
    stage: str
    final_result: str | None = None
    resolution_mode: ResolutionMode
    voice_call_id: str | None = None
    voice_call_status: str | None = None


router = APIRouter(prefix="/workflows", tags=["workflows"])


async def _submit_borrower_message(
    payload: WorkflowMessageRequest,
    default_resolution_mode: ResolutionMode,
) -> WorkflowMessageResponse:
    try:
        state = await borrower_conversation_service.submit_borrower_message(
            borrower_id=payload.borrower_id,
            workflow_id=payload.workflow_id,
            message=payload.message,
            resolution_mode=payload.resolution_mode,
            prompt_version_overrides=payload.prompt_version_overrides,
            default_resolution_mode=default_resolution_mode,
        )
    except Exception as error:
        if "not found" in str(error).lower():
            raise HTTPException(status_code=404, detail=str(error)) from error
        raise HTTPException(status_code=500, detail=str(error)) from error

    return WorkflowMessageResponse(
        workflow_id=state.borrower_case.workflow_id,
        reply=state.last_agent_reply,
        stage=state.borrower_case.stage.value,
        final_result=state.final_result,
        resolution_mode=state.borrower_case.resolution_mode,
        voice_call_id=state.borrower_case.resolution_call_id,
        voice_call_status=state.borrower_case.resolution_call_status,
    )


@router.post("/messages", response_model=WorkflowMessageResponse)
async def submit_borrower_message(payload: WorkflowMessageRequest) -> WorkflowMessageResponse:
    return await _submit_borrower_message(payload, DEFAULT_BORROWER_RESOLUTION_MODE)


@router.post("/test/messages", response_model=WorkflowMessageResponse)
async def submit_tester_message(payload: WorkflowMessageRequest) -> WorkflowMessageResponse:
    return await _submit_borrower_message(payload, DEFAULT_TESTER_RESOLUTION_MODE)


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
