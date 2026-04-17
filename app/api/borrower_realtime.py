from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.domain.borrower_case import ResolutionMode
from app.realtime.hub import borrower_realtime_hub
from app.realtime.models import BorrowerSocketClientMessage
from app.services.borrower_conversation import borrower_conversation_service
from app.services.workflow_channel import DEFAULT_BORROWER_RESOLUTION_MODE


router = APIRouter(prefix="/borrower-realtime", tags=["borrower-realtime"])


@router.websocket("/ws/{borrower_id}")
async def borrower_realtime_socket(websocket: WebSocket, borrower_id: str) -> None:
    await borrower_realtime_hub.connect(borrower_id, websocket)
    try:
        state = borrower_conversation_service.build_conversation_state(borrower_id)
        await borrower_realtime_hub.send_state(websocket, state)

        while True:
            payload = BorrowerSocketClientMessage.model_validate_json(await websocket.receive_text())
            if payload.type != "borrower_message":
                await borrower_realtime_hub.send_error(websocket, "Unsupported borrower websocket event")
                continue
            if not borrower_conversation_service.can_accept_borrower_message(borrower_id):
                state = borrower_conversation_service.build_conversation_state(borrower_id)
                await borrower_realtime_hub.send_error(
                    websocket,
                    "Borrower messaging is currently unavailable while the voice resolution step is in progress.",
                )
                await borrower_realtime_hub.send_state(websocket, state)
                continue

            workflow_state = await borrower_conversation_service.submit_borrower_message(
                borrower_id=borrower_id,
                workflow_id=None,
                message=payload.message,
                resolution_mode=ResolutionMode.VOICE,
                default_resolution_mode=DEFAULT_BORROWER_RESOLUTION_MODE,
            )
            state = borrower_conversation_service.build_conversation_state(
                borrower_id,
                workflow_state=workflow_state,
            )
            await borrower_realtime_hub.publish_state(borrower_id, state)
    except WebSocketDisconnect:
        await borrower_realtime_hub.disconnect(borrower_id, websocket)
    except Exception as error:
        try:
            await borrower_realtime_hub.send_error(websocket, str(error))
        finally:
            await borrower_realtime_hub.disconnect(borrower_id, websocket)
            await websocket.close()
