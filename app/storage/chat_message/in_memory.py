from __future__ import annotations

from app.domain.chat_message import ChatMessage
from app.storage.chat_message.base import ChatMessageStorage


class InMemoryChatMessageStorage(ChatMessageStorage):
    def __init__(self) -> None:
        self.messages: list[ChatMessage] = []

    def append_message(self, chat_message: ChatMessage) -> ChatMessage:
        self.messages.append(chat_message)
        return chat_message

    def list_messages(self, user_id: str, workflow_id: str, agent_id: str) -> list[ChatMessage]:
        return [
            message
            for message in self.messages
            if (
                message.user_id == user_id
                and message.workflow_id == workflow_id
                and message.agent_id == agent_id
            )
        ]

    def list_workflow_messages(self, user_id: str, workflow_id: str) -> list[ChatMessage]:
        return [
            message
            for message in self.messages
            if message.user_id == user_id and message.workflow_id == workflow_id
        ]
