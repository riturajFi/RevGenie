from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.chat_message import ChatMessage


class ChatMessageStorage(ABC):
    @abstractmethod
    def append_chat_message(self, chat_message: ChatMessage) -> ChatMessage:
        raise NotImplementedError

    @abstractmethod
    def list_chat_messages_for_user(self, user_id: str) -> list[ChatMessage]:
        raise NotImplementedError
