from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.domain.chat_message import ChatMessage
from app.storage.chat_message.base import ChatMessageStorage
from app.storage.chat_message.json_file import JsonFileChatMessageStorage


class ChatMessageService(ABC):
    @abstractmethod
    def append_chat_message(self, user_id: str, chat_message: str) -> ChatMessage:
        raise NotImplementedError

    @abstractmethod
    def list_chat_messages_for_conversation(self, borrower_id: str) -> list[ChatMessage]:
        raise NotImplementedError


class FileChatMessageService(ChatMessageService):
    def __init__(self, file_path: str = "data/chat_messages.json") -> None:
        self.storage: ChatMessageStorage = JsonFileChatMessageStorage(file_path)

    def append_chat_message(self, user_id: str, chat_message: str) -> ChatMessage:
        message = ChatMessage(
            user_id=user_id,
            chat_message=chat_message,
            created_at=datetime.now(timezone.utc),
        )
        return self.storage.append_chat_message(message)

    def list_chat_messages_for_conversation(self, borrower_id: str) -> list[ChatMessage]:
        borrower_messages = self.storage.list_chat_messages_for_user(borrower_id)
        agent_messages = self.storage.list_chat_messages_for_user(self._agent_user_id(borrower_id))
        return sorted(
            borrower_messages + agent_messages,
            key=lambda message: message.created_at,
        )

    def _agent_user_id(self, borrower_id: str) -> str:
        return f"agent:{borrower_id}"
