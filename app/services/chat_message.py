from __future__ import annotations

from datetime import datetime, timezone

from app.domain.chat_message import ChatMessage
from app.storage.chat_message.base import ChatMessageStorage
from app.storage.chat_message.in_memory import InMemoryChatMessageStorage


class ChatMessageService:
    def __init__(self, storage: ChatMessageStorage) -> None:
        self.storage = storage

    def append_message(
        self,
        user_id: str,
        agent_id: str,
        sender_type: str,
        message: str,
    ) -> ChatMessage:
        chat_message = ChatMessage(
            message=message,
            user_id=user_id,
            agent_id=agent_id,
            sender_type=sender_type,
            created_at=datetime.now(timezone.utc),
        )
        return self.storage.append_message(chat_message)

    def list_messages(self, user_id: str, agent_id: str) -> list[ChatMessage]:
        messages = self.storage.list_messages(user_id, agent_id)
        return sorted(messages, key=lambda item: item.created_at)

    def append_handoff_message(self, user_id: str, agent_id: str, summary: str | None) -> None:
        if not summary:
            return
        if self.list_messages(user_id, agent_id):
            return
        self.append_message(
            user_id=user_id,
            agent_id=agent_id,
            sender_type="system",
            message=summary,
        )


_chat_message_service = ChatMessageService(storage=InMemoryChatMessageStorage())


def get_chat_message_service() -> ChatMessageService:
    return _chat_message_service
