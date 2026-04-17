from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.realtime.hub import borrower_realtime_hub
from app.services.borrower_conversation import borrower_conversation_service
from app.services.retell import RetellService, RetellWebhookVerificationError


router = APIRouter(prefix="/retell-webhooks", tags=["retell-webhooks"])
retell_service = RetellService()


class RetellWebhookPayload(BaseModel):
    event: str
    call: dict[str, Any]


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
async def handle_retell_event(request: Request) -> Response:
    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8")

    try:
        retell_service.verify_webhook_signature(raw_text, request.headers.get("x-retell-signature"))
    except RetellWebhookVerificationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error

    payload = RetellWebhookPayload.model_validate_json(raw_text)
    if payload.event != "call_analyzed":
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        workflow_state = await borrower_conversation_service.submit_resolution_call_completion(payload.call)
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

    if workflow_state is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    state = borrower_conversation_service.build_conversation_state(
        workflow_state.borrower_case.borrower_id,
        workflow_state=workflow_state,
    )
    await borrower_realtime_hub.publish_state(
        workflow_state.borrower_case.borrower_id,
        state,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
