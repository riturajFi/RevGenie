from __future__ import annotations

from temporalio import activity

from app.agents.assessment.agent import AssessmentAgent
from app.agents.final_notice.agent import FinalNoticeAgent
from app.agents.resolution.agent import ResolutionAgent
from app.domain.borrower_case import AgentTurnResult, BorrowerCase, ContactChannel, Stage
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_case_state import BorrowerCaseStateService
from app.services.chat_message import get_chat_message_service
from app.temporal.models import (
    AgentPromptActivityInput,
    AgentTurnActivityInput,
    AgentTurnActivityResult,
)


borrower_case_service = FileBorrowerCaseService()
borrower_case_state_service = BorrowerCaseStateService()
chat_message_service = get_chat_message_service()


def _load_case(borrower_id: str) -> BorrowerCase:
    borrower_case = borrower_case_service.get_borrower_case(borrower_id)
    if borrower_case is None:
        raise ValueError(f"Borrower case not found for {borrower_id}")
    return borrower_case


def _save_case(borrower_case: BorrowerCase) -> BorrowerCase:
    return borrower_case_service.update_borrower_case(borrower_case.borrower_id, borrower_case)


def _append_message(borrower_id: str, stage: Stage, sender_type: str, message: str) -> None:
    chat_message_service.append_message(
        user_id=borrower_id,
        agent_id=stage.value,
        sender_type=sender_type,
        message=message,
    )


def _list_stage_messages(borrower_id: str, stage: Stage):
    return chat_message_service.list_messages(user_id=borrower_id, agent_id=stage.value)


def _ensure_handoff_message(borrower_case: BorrowerCase, stage: Stage) -> None:
    chat_message_service.append_handoff_message(
        user_id=borrower_case.borrower_id,
        agent_id=stage.value,
        summary=borrower_case.latest_handoff_summary,
    )


@activity.defn
def load_borrower_case(borrower_id: str) -> BorrowerCase:
    return _load_case(borrower_id)


@activity.defn
def save_borrower_case(borrower_case: BorrowerCase) -> BorrowerCase:
    return _save_case(borrower_case)


@activity.defn
def send_assessment_prompt(input: AgentPromptActivityInput) -> str:
    borrower_case = input.borrower_case
    chat_history = _list_stage_messages(borrower_case.borrower_id, Stage.ASSESSMENT)
    agent = AssessmentAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke_with_instruction(
        borrower_id=borrower_case.borrower_id,
        borrower_case=borrower_case,
        instruction=input.instruction,
        chat_history=chat_history,
    )
    _append_message(borrower_case.borrower_id, Stage.ASSESSMENT, "agent", result.reply)
    return result.reply


@activity.defn
def run_assessment_turn(input: AgentTurnActivityInput) -> AgentTurnActivityResult:
    borrower_case = input.borrower_case
    chat_history = _list_stage_messages(borrower_case.borrower_id, Stage.ASSESSMENT)
    _append_message(borrower_case.borrower_id, Stage.ASSESSMENT, "borrower", input.message)
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
    _append_message(borrower_case.borrower_id, Stage.ASSESSMENT, "agent", result.reply)
    return AgentTurnActivityResult(
        borrower_case=updated_case,
        stage_result=result,
    )


@activity.defn
def send_resolution_prompt(input: AgentPromptActivityInput) -> str:
    borrower_case = input.borrower_case
    _ensure_handoff_message(borrower_case, Stage.RESOLUTION)
    chat_history = _list_stage_messages(borrower_case.borrower_id, Stage.RESOLUTION)
    agent = ResolutionAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke_with_instruction(
        borrower_id=borrower_case.borrower_id,
        borrower_case=borrower_case,
        instruction=input.instruction,
        chat_history=chat_history,
    )
    _append_message(borrower_case.borrower_id, Stage.RESOLUTION, "agent", result.reply)
    return result.reply


@activity.defn
def run_resolution_turn(input: AgentTurnActivityInput) -> AgentTurnActivityResult:
    borrower_case = input.borrower_case
    _ensure_handoff_message(borrower_case, Stage.RESOLUTION)
    chat_history = _list_stage_messages(borrower_case.borrower_id, Stage.RESOLUTION)
    _append_message(borrower_case.borrower_id, Stage.RESOLUTION, "borrower", input.message)
    agent = ResolutionAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke(
        borrower_id=borrower_case.borrower_id,
        message=input.message,
        borrower_case=borrower_case,
        chat_history=chat_history,
    )
    updated_case = borrower_case_state_service.apply_delta(
        borrower_case=borrower_case,
        case_delta=result.case_delta,
        stage=Stage.RESOLUTION,
        latest_handoff_summary=result.latest_handoff_summary,
    )
    updated_case.stage = Stage.RESOLUTION
    updated_case.last_contact_channel = ContactChannel.CHAT
    _append_message(borrower_case.borrower_id, Stage.RESOLUTION, "agent", result.reply)
    return AgentTurnActivityResult(
        borrower_case=updated_case,
        stage_result=result,
    )


@activity.defn
def send_final_notice_prompt(input: AgentPromptActivityInput) -> str:
    borrower_case = input.borrower_case
    _ensure_handoff_message(borrower_case, Stage.FINAL_NOTICE)
    chat_history = _list_stage_messages(borrower_case.borrower_id, Stage.FINAL_NOTICE)
    agent = FinalNoticeAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke_with_instruction(
        borrower_id=borrower_case.borrower_id,
        borrower_case=borrower_case,
        instruction=input.instruction,
        chat_history=chat_history,
    )
    _append_message(borrower_case.borrower_id, Stage.FINAL_NOTICE, "agent", result.reply)
    return result.reply


@activity.defn
def run_final_notice_turn(input: AgentTurnActivityInput) -> AgentTurnActivityResult:
    borrower_case = input.borrower_case
    _ensure_handoff_message(borrower_case, Stage.FINAL_NOTICE)
    chat_history = _list_stage_messages(borrower_case.borrower_id, Stage.FINAL_NOTICE)
    _append_message(borrower_case.borrower_id, Stage.FINAL_NOTICE, "borrower", input.message)
    agent = FinalNoticeAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke(
        borrower_id=borrower_case.borrower_id,
        message=input.message,
        borrower_case=borrower_case,
        chat_history=chat_history,
    )
    updated_case = borrower_case_state_service.apply_delta(
        borrower_case=borrower_case,
        case_delta=result.case_delta,
        stage=Stage.FINAL_NOTICE,
        latest_handoff_summary=result.latest_handoff_summary,
    )
    updated_case.stage = Stage.FINAL_NOTICE
    updated_case.last_contact_channel = ContactChannel.CHAT
    _append_message(borrower_case.borrower_id, Stage.FINAL_NOTICE, "agent", result.reply)
    return AgentTurnActivityResult(
        borrower_case=updated_case,
        stage_result=result,
    )
