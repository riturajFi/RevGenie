from __future__ import annotations

from app.services.chat_message import ChatMessageService
from app.storage.chat_message.in_memory import InMemoryChatMessageStorage


def test_list_messages_is_scoped_by_workflow_id() -> None:
    service = ChatMessageService(storage=InMemoryChatMessageStorage())

    service.append_message(
        user_id="b_001",
        workflow_id="wf_old",
        agent_id="ASSESSMENT",
        sender_type="borrower",
        message="old workflow message",
    )
    service.append_message(
        user_id="b_001",
        workflow_id="wf_new",
        agent_id="ASSESSMENT",
        sender_type="borrower",
        message="new workflow message",
    )

    old_messages = service.list_messages(
        user_id="b_001",
        workflow_id="wf_old",
        agent_id="ASSESSMENT",
    )
    new_messages = service.list_messages(
        user_id="b_001",
        workflow_id="wf_new",
        agent_id="ASSESSMENT",
    )

    assert [message.message for message in old_messages] == ["old workflow message"]
    assert [message.message for message in new_messages] == ["new workflow message"]


def test_handoff_message_is_scoped_by_workflow_id() -> None:
    service = ChatMessageService(storage=InMemoryChatMessageStorage())

    service.append_message(
        user_id="b_001",
        workflow_id="wf_old",
        agent_id="RESOLUTION",
        sender_type="borrower",
        message="existing resolution history",
    )

    service.append_handoff_message(
        user_id="b_001",
        workflow_id="wf_new",
        agent_id="RESOLUTION",
        summary="fresh handoff summary",
    )

    new_messages = service.list_messages(
        user_id="b_001",
        workflow_id="wf_new",
        agent_id="RESOLUTION",
    )

    assert len(new_messages) == 1
    assert new_messages[0].sender_type == "system"
    assert new_messages[0].message == "fresh handoff summary"
