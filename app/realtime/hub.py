from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket

from app.realtime.models import BorrowerConversationState, BorrowerSocketServerEvent


class BorrowerRealtimeHub:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, borrower_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[borrower_id].add(websocket)

    async def disconnect(self, borrower_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(borrower_id)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(borrower_id, None)

    async def send_state(self, websocket: WebSocket, state: BorrowerConversationState) -> None:
        event = BorrowerSocketServerEvent(type="conversation_state", state=state)
        await websocket.send_json(event.model_dump(mode="json"))

    async def send_error(self, websocket: WebSocket, message: str) -> None:
        event = BorrowerSocketServerEvent(type="error", message=message)
        await websocket.send_json(event.model_dump(mode="json"))

    async def publish_state(self, borrower_id: str, state: BorrowerConversationState) -> None:
        async with self._lock:
            targets = list(self._connections.get(borrower_id, set()))

        stale_connections: list[WebSocket] = []
        for websocket in targets:
            try:
                await self.send_state(websocket, state)
            except Exception:
                stale_connections.append(websocket)

        for websocket in stale_connections:
            await self.disconnect(borrower_id, websocket)


borrower_realtime_hub = BorrowerRealtimeHub()
