from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.orchestrator.client import get_temporal_client
from app.orchestrator.models import ResolutionVoiceCallCompletedInput
from app.orchestrator.workflows import BorrowerCollectionsWorkflow
from app.services.borrower_case import FileBorrowerCaseService
from app.services.retell import RetellService, RetellWebhookVerificationError


router = APIRouter(prefix="/retell-webhooks", tags=["retell-webhooks"])
retell_service = RetellService()
borrower_case_service = FileBorrowerCaseService()


class RetellWebhookPayload(BaseModel):
    event: str
    call: dict[str, Any]


def _resolve_workflow_id(call: dict[str, Any]) -> str | None:
    metadata = call.get("metadata")
    if isinstance(metadata, dict):
        workflow_id = metadata.get("workflow_id")
        if isinstance(workflow_id, str) and workflow_id.strip():
            return workflow_id.strip()
        borrower_id = metadata.get("borrower_id")
        if isinstance(borrower_id, str) and borrower_id.strip():
            borrower_case = borrower_case_service.get_borrower_case(borrower_id.strip())
            if borrower_case is not None:
                return borrower_case.workflow_id

    incoming_call_id = str(call.get("call_id") or "").strip()
    if not incoming_call_id:
        return None
    for borrower_case in borrower_case_service.list_borrower_cases():
        if borrower_case.resolution_call_id == incoming_call_id:
            return borrower_case.workflow_id
    return None


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
async def handle_retell_event(request: Request) -> Response:
    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8")

    try:
        retell_service.verify_webhook_signature(raw_text, request.headers.get("x-retell-signature"))
    except RetellWebhookVerificationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

    payload = RetellWebhookPayload.model_validate_json(raw_text)
    if payload.event not in {"call_ended", "call_analyzed"}:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    workflow_id = _resolve_workflow_id(payload.call)
    if not workflow_id:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    try:
        await handle.execute_update(
            BorrowerCollectionsWorkflow.handle_resolution_call_completed,
            ResolutionVoiceCallCompletedInput(call=payload.call),
        )
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
