from __future__ import annotations

import os
from datetime import datetime, timezone

from app.domain.chat_message import ChatMessage
from app.storage.chat_message.base import ChatMessageStorage
from app.storage.chat_message.json_file import JsonFileChatMessageStorage


class ChatMessageService:
    def __init__(self, storage: ChatMessageStorage) -> None:
        self.storage = storage

    def append_message(
        self,
        user_id: str,
        workflow_id: str,
        agent_id: str,
        sender_type: str,
        message: str,
        visible_to_borrower: bool = True,
    ) -> ChatMessage:
        chat_message = ChatMessage(
            message=message,
            user_id=user_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
            sender_type=sender_type,
            visible_to_borrower=visible_to_borrower,
            created_at=datetime.now(timezone.utc),
        )
        return self.storage.append_message(chat_message)

    def list_messages(self, user_id: str, workflow_id: str, agent_id: str) -> list[ChatMessage]:
        messages = self.storage.list_messages(user_id, workflow_id, agent_id)
        return sorted(messages, key=lambda item: item.created_at)

    def list_workflow_messages(self, user_id: str, workflow_id: str) -> list[ChatMessage]:
        messages = self.storage.list_workflow_messages(user_id, workflow_id)
        return sorted(messages, key=lambda item: item.created_at)

    def list_visible_workflow_messages(self, user_id: str, workflow_id: str) -> list[ChatMessage]:
        return [
            item
            for item in self.list_workflow_messages(user_id, workflow_id)
            if item.visible_to_borrower
        ]

    def append_handoff_message(
        self,
        user_id: str,
        workflow_id: str,
        agent_id: str,
        summary: str | None,
    ) -> None:
        if not summary:
            return
        if self.list_messages(user_id, workflow_id, agent_id):
            return
        self.append_message(
            user_id=user_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
            sender_type="system",
            message=summary,
            visible_to_borrower=False,
        )


_chat_message_service = ChatMessageService(
    storage=JsonFileChatMessageStorage(os.getenv("CHAT_MESSAGE_FILE", "data/app/chat_messages.json"))
)


def get_chat_message_service() -> ChatMessageService:
    return _chat_message_service
