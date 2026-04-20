from __future__ import annotations

import json
from pathlib import Path

from app.domain.chat_message import ChatMessage
from app.storage.chat_message.base import ChatMessageStorage


class JsonFileChatMessageStorage(ChatMessageStorage):
    def __init__(self, file_path: str = "data/app/chat_messages.json") -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def append_message(self, chat_message: ChatMessage) -> ChatMessage:
        records = self._read()
        records.append(chat_message.model_dump(mode="json"))
        self._write(records)
        return chat_message

    def list_messages(self, user_id: str, workflow_id: str, agent_id: str) -> list[ChatMessage]:
        return [
            message
            for record in self._read()
            for message in [ChatMessage.model_validate(record)]
            if message.user_id == user_id and message.workflow_id == workflow_id and message.agent_id == agent_id
        ]

    def list_workflow_messages(self, user_id: str, workflow_id: str) -> list[ChatMessage]:
        return [
            message
            for record in self._read()
            for message in [ChatMessage.model_validate(record)]
            if message.user_id == user_id and message.workflow_id == workflow_id
        ]

    def list_all_messages(self) -> list[ChatMessage]:
        return [ChatMessage.model_validate(record) for record in self._read()]

    def _read(self) -> list[dict]:
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write(self, records: list[dict]) -> None:
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2)
        temp_path.replace(self.path)
