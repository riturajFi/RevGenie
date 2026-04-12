from __future__ import annotations

from temporalio import activity

from app.agents.assessment.agent import AssessmentAgent
from app.agents.final_notice.agent import FinalNoticeAgent
from app.agents.resolution.agent import ResolutionAgent
from app.domain.borrower_case import AgentTurnResult, BorrowerCase, ContactChannel, Stage
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_case_state import BorrowerCaseStateService
from app.services.chat_message import FileChatMessageService
from app.temporal.models import (
    AgentPromptActivityInput,
    AgentTurnActivityInput,
    AgentTurnActivityResult,
)


borrower_case_service = FileBorrowerCaseService()
borrower_case_state_service = BorrowerCaseStateService()
chat_message_service = FileChatMessageService()


def _load_case(borrower_id: str) -> BorrowerCase:
    borrower_case = borrower_case_service.get_borrower_case(borrower_id)
    if borrower_case is None:
        raise ValueError(f"Borrower case not found for {borrower_id}")
    return borrower_case


def _save_case(borrower_case: BorrowerCase) -> BorrowerCase:
    return borrower_case_service.update_borrower_case(borrower_case.borrower_id, borrower_case)


def _append_agent_reply(borrower_id: str, reply: str) -> None:
    chat_message_service.append_chat_message(user_id=f"agent:{borrower_id}", chat_message=reply)


def _append_borrower_message(borrower_id: str, message: str) -> None:
    chat_message_service.append_chat_message(user_id=borrower_id, chat_message=message)


@activity.defn
def load_borrower_case(borrower_id: str) -> BorrowerCase:
    return _load_case(borrower_id)


@activity.defn
def save_borrower_case(borrower_case: BorrowerCase) -> BorrowerCase:
    return _save_case(borrower_case)


@activity.defn
def send_assessment_prompt(input: AgentPromptActivityInput) -> str:
    borrower_case = input.borrower_case
    chat_history = chat_message_service.list_chat_messages_for_conversation(borrower_case.borrower_id)
    agent = AssessmentAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke_with_instruction(
        borrower_id=borrower_case.borrower_id,
        borrower_case=borrower_case,
        instruction=input.instruction,
        chat_history=chat_history,
    )
    _append_agent_reply(borrower_case.borrower_id, result.reply)
    return result.reply


@activity.defn
def run_assessment_turn(input: AgentTurnActivityInput) -> AgentTurnActivityResult:
    borrower_case = input.borrower_case
    chat_history = chat_message_service.list_chat_messages_for_conversation(borrower_case.borrower_id)
    _append_borrower_message(borrower_case.borrower_id, input.message)
    agent = AssessmentAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke(
        borrower_id=borrower_case.borrower_id,
        message=input.message,
        borrower_case=borrower_case,
        chat_history=chat_history,
    )
    updated_case = borrower_case_state_service.apply_delta(
        borrower_case=borrower_case,
        case_delta=result.case_delta,
        stage=Stage.ASSESSMENT,
        latest_handoff_summary=result.latest_handoff_summary,
    )
    updated_case.stage = Stage.ASSESSMENT
    updated_case.last_contact_channel = ContactChannel.CHAT
    _append_agent_reply(borrower_case.borrower_id, result.reply)
    return AgentTurnActivityResult(
        borrower_case=updated_case,
        stage_result=result,
    )


@activity.defn
def send_resolution_prompt(input: AgentPromptActivityInput) -> str:
    borrower_case = input.borrower_case
    agent = ResolutionAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke_with_instruction(
        borrower_id=borrower_case.borrower_id,
        assessment_summary=borrower_case.latest_handoff_summary or "",
        borrower_case=borrower_case,
        instruction=input.instruction,
    )
    _append_agent_reply(borrower_case.borrower_id, result.reply)
    return result.reply


@activity.defn
def run_resolution_turn(input: AgentTurnActivityInput) -> AgentTurnActivityResult:
    borrower_case = input.borrower_case
    _append_borrower_message(borrower_case.borrower_id, input.message)
    agent = ResolutionAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke(
        borrower_id=borrower_case.borrower_id,
        assessment_summary=borrower_case.latest_handoff_summary or "",
        message=input.message,
        borrower_case=borrower_case,
    )
    updated_case = borrower_case_state_service.apply_delta(
        borrower_case=borrower_case,
        case_delta=result.case_delta,
        stage=Stage.RESOLUTION,
        latest_handoff_summary=result.latest_handoff_summary,
    )
    updated_case.stage = Stage.RESOLUTION
    updated_case.last_contact_channel = ContactChannel.CHAT
    _append_agent_reply(borrower_case.borrower_id, result.reply)
    return AgentTurnActivityResult(
        borrower_case=updated_case,
        stage_result=result,
    )


@activity.defn
def send_final_notice_prompt(input: AgentPromptActivityInput) -> str:
    borrower_case = input.borrower_case
    agent = FinalNoticeAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke_with_instruction(
        borrower_id=borrower_case.borrower_id,
        resolution_summary=borrower_case.latest_handoff_summary or "",
        borrower_case=borrower_case,
        instruction=input.instruction,
    )
    _append_agent_reply(borrower_case.borrower_id, result.reply)
    return result.reply


@activity.defn
def run_final_notice_turn(input: AgentTurnActivityInput) -> AgentTurnActivityResult:
    borrower_case = input.borrower_case
    _append_borrower_message(borrower_case.borrower_id, input.message)
    agent = FinalNoticeAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke(
        borrower_id=borrower_case.borrower_id,
        resolution_summary=borrower_case.latest_handoff_summary or "",
        message=input.message,
        borrower_case=borrower_case,
    )
    updated_case = borrower_case_state_service.apply_delta(
        borrower_case=borrower_case,
        case_delta=result.case_delta,
        stage=Stage.FINAL_NOTICE,
        latest_handoff_summary=result.latest_handoff_summary,
    )
    updated_case.stage = Stage.FINAL_NOTICE
    updated_case.last_contact_channel = ContactChannel.CHAT
    _append_agent_reply(borrower_case.borrower_id, result.reply)
    return AgentTurnActivityResult(
        borrower_case=updated_case,
        stage_result=result,
    )
