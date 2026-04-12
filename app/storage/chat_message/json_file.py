from __future__ import annotations

import json
from pathlib import Path

from app.domain.chat_message import ChatMessage
from app.storage.chat_message.base import ChatMessageStorage


class JsonFileChatMessageStorage(ChatMessageStorage):
    def __init__(self, file_path: str = "data/chat_messages.json") -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def append_message(self, chat_message: ChatMessage) -> ChatMessage:
        records = self._read()
        records.append(chat_message.model_dump(mode="json"))
        self._write(records)
        return chat_message

    def list_messages(self, user_id: str, agent_id: str) -> list[ChatMessage]:
        messages = [ChatMessage.model_validate(item) for item in self._read()]
        return [
            message
            for message in messages
            if message.user_id == user_id and message.agent_id == agent_id
        ]

    def _read(self) -> list[dict]:
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write(self, records: list[dict]) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2)
