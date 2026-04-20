from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.chat_message import ChatMessage


class ChatMessageStorage(ABC):
    @abstractmethod
    def append_message(self, chat_message: ChatMessage) -> ChatMessage:
        raise NotImplementedError

    @abstractmethod
    def list_messages(self, user_id: str, workflow_id: str, agent_id: str) -> list[ChatMessage]:
        raise NotImplementedError

    @abstractmethod
    def list_workflow_messages(self, user_id: str, workflow_id: str) -> list[ChatMessage]:
        raise NotImplementedError

    @abstractmethod
    def list_all_messages(self) -> list[ChatMessage]:
        raise NotImplementedError
