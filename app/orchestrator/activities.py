from __future__ import annotations

from typing import Any

from temporalio import activity

from app.agents.assessment.agent import AssessmentAgent
from app.agents.final_notice.agent import FinalNoticeAgent
from app.agents.resolution.agent import ResolutionAgent
from app.domain.borrower_case import AgentStageOutcome, AgentTurnResult, BorrowerCase, ContactChannel, Stage
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_case_state import BorrowerCaseStateService
from app.services.borrower_profile import FileBorrowerProfileService
from app.services.chat_message import get_chat_message_service
from app.services.retell import RetellService
from app.orchestrator.models import (
    AgentTurnActivityInput,
    AgentTurnActivityResult,
    ResolutionCallActivityInput,
    StartResolutionCallResult,
)


borrower_case_service = FileBorrowerCaseService()
borrower_case_state_service = BorrowerCaseStateService()
borrower_profile_service = FileBorrowerProfileService()
chat_message_service = get_chat_message_service()
retell_service = RetellService()


def _load_case(borrower_id: str) -> BorrowerCase:
    borrower_case = borrower_case_service.get_borrower_case(borrower_id)
    if borrower_case is None:
        raise ValueError(f"Borrower case not found for {borrower_id}")
    return borrower_case


def _save_case(borrower_case: BorrowerCase) -> BorrowerCase:
    return borrower_case_service.update_borrower_case(borrower_case.borrower_id, borrower_case)


def _append_message(borrower_case: BorrowerCase, stage: Stage, sender_type: str, message: str) -> None:
    chat_message_service.append_message(
        user_id=borrower_case.borrower_id,
        workflow_id=borrower_case.workflow_id,
        agent_id=stage.value,
        sender_type=sender_type,
        message=message,
    )


def _list_stage_messages(borrower_case: BorrowerCase, stage: Stage):
    return chat_message_service.list_messages(
        user_id=borrower_case.borrower_id,
        workflow_id=borrower_case.workflow_id,
        agent_id=stage.value,
    )


def _ensure_handoff_message(borrower_case: BorrowerCase, stage: Stage) -> None:
    chat_message_service.append_handoff_message(
        user_id=borrower_case.borrower_id,
        workflow_id=borrower_case.workflow_id,
        agent_id=stage.value,
        summary=borrower_case.latest_handoff_summary,
    )


def _normalize_turn_text(turn: dict[str, Any]) -> str:
    return str(
        turn.get("content")
        or turn.get("message")
        or turn.get("transcript")
        or turn.get("utterance")
        or ""
    ).strip()


def _normalize_turn_role(turn: dict[str, Any]) -> str:
    return str(
        turn.get("role")
        or turn.get("speaker")
        or turn.get("name")
        or turn.get("participant")
        or ""
    ).strip().lower()


def _extract_transcript_turns(call: dict[str, Any]) -> list[tuple[str, str]]:
    raw_turns = call.get("transcript_object")
    if not isinstance(raw_turns, list) or not raw_turns:
        raw_turns = call.get("transcript_with_tool_calls")
    if not isinstance(raw_turns, list):
        raw_turns = []

    turns: list[tuple[str, str]] = []
    for item in raw_turns:
        if not isinstance(item, dict):
            continue
        text = _normalize_turn_text(item)
        if not text:
            continue
        role = _normalize_turn_role(item)
        if role in {"agent", "assistant", "ai"}:
            sender_type = "agent"
        elif role in {"user", "caller", "borrower", "customer"}:
            sender_type = "borrower"
        else:
            sender_type = "agent" if len(turns) % 2 else "borrower"
        turns.append((sender_type, text))

    if turns:
        return turns

    transcript = str(call.get("transcript") or "").strip()
    if transcript:
        return [("borrower", transcript)]
    return []


def _transcript_as_text(turns: list[tuple[str, str]]) -> str:
    return "\n".join(f"{sender_type.upper()}: {text}" for sender_type, text in turns)


@activity.defn
def load_borrower_case(borrower_id: str) -> BorrowerCase:
    return _load_case(borrower_id)


@activity.defn
def save_borrower_case(borrower_case: BorrowerCase) -> BorrowerCase:
    return _save_case(borrower_case)


@activity.defn
def run_assessment_turn(input: AgentTurnActivityInput) -> AgentTurnActivityResult:
    borrower_case = input.borrower_case
    chat_history = _list_stage_messages(borrower_case, Stage.ASSESSMENT)
    _append_message(borrower_case, Stage.ASSESSMENT, "borrower", input.message)
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
    _append_message(borrower_case, Stage.ASSESSMENT, "agent", result.reply)
    return AgentTurnActivityResult(
        borrower_case=updated_case,
        stage_result=result,
    )


@activity.defn
def run_resolution_turn(input: AgentTurnActivityInput) -> AgentTurnActivityResult:
    borrower_case = input.borrower_case
    _ensure_handoff_message(borrower_case, Stage.RESOLUTION)
    chat_history = _list_stage_messages(borrower_case, Stage.RESOLUTION)
    _append_message(borrower_case, Stage.RESOLUTION, "borrower", input.message)
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
    _append_message(borrower_case, Stage.RESOLUTION, "agent", result.reply)
    return AgentTurnActivityResult(
        borrower_case=updated_case,
        stage_result=result,
    )


@activity.defn
def run_final_notice_turn(input: AgentTurnActivityInput) -> AgentTurnActivityResult:
    borrower_case = input.borrower_case
    _ensure_handoff_message(borrower_case, Stage.FINAL_NOTICE)
    chat_history = _list_stage_messages(borrower_case, Stage.FINAL_NOTICE)
    _append_message(borrower_case, Stage.FINAL_NOTICE, "borrower", input.message)
    agent = FinalNoticeAgent(lender_id=borrower_case.lender_id)
    result = agent.invoke(
        borrower_id=borrower_case.borrower_id,
        message=input.message,
        borrower_case=borrower_case,
        chat_history=chat_history,
    )
    if not result.reply.strip():
        if result.stage_outcome == AgentStageOutcome.NO_RESOLUTION:
            result.reply = (
                "I have recorded your request to close this out and stop contact. "
                "This case will be closed with no further outreach."
            )
        elif result.stage_outcome == AgentStageOutcome.RESOLVED:
            result.reply = "I have recorded the resolution and this case is now closed."
        else:
            result.reply = "I have recorded your message for final processing."
    updated_case = borrower_case_state_service.apply_delta(
        borrower_case=borrower_case,
        case_delta=result.case_delta,
        stage=Stage.FINAL_NOTICE,
        latest_handoff_summary=result.latest_handoff_summary,
    )
    updated_case.stage = Stage.FINAL_NOTICE
    updated_case.last_contact_channel = ContactChannel.CHAT
    _append_message(borrower_case, Stage.FINAL_NOTICE, "agent", result.reply)
    return AgentTurnActivityResult(
        borrower_case=updated_case,
        stage_result=result,
    )


@activity.defn
def start_resolution_call(borrower_case: BorrowerCase) -> StartResolutionCallResult:
    _ensure_handoff_message(borrower_case, Stage.RESOLUTION)
    borrower_profile = borrower_profile_service.get_borrower_profile(borrower_case.borrower_id)
    if borrower_profile is None:
        raise ValueError(f"Borrower profile not found for {borrower_case.borrower_id}")

    call = retell_service.place_phone_call(
        borrower_case=borrower_case,
        borrower_profile=borrower_profile,
        handoff_summary=borrower_case.latest_handoff_summary,
    )
    call_id = str(call.get("call_id") or "")
    if not call_id:
        raise ValueError("Retell did not return call_id")

    return StartResolutionCallResult(
        call_id=call_id,
        call_status=str(call.get("call_status") or ""),
    )


@activity.defn
def finalize_resolution_call(input: ResolutionCallActivityInput) -> AgentTurnActivityResult:
    borrower_case = input.borrower_case
    call = input.call
    _ensure_handoff_message(borrower_case, Stage.RESOLUTION)
    chat_history = _list_stage_messages(borrower_case, Stage.RESOLUTION)
    transcript_turns = _extract_transcript_turns(call)
    transcript_text = _transcript_as_text(transcript_turns)

    if transcript_text:
        agent = ResolutionAgent(lender_id=borrower_case.lender_id)
        result = agent.analyze_completed_voice_call(
            borrower_id=borrower_case.borrower_id,
            borrower_case=borrower_case,
            transcript=transcript_text,
            chat_history=chat_history,
        )
    else:
        result = AgentTurnResult(
            reply="",
            stage_outcome=AgentStageOutcome.NO_DEAL,
            case_delta={},
            latest_handoff_summary=(
                "Agent 2 attempted a voice call but no usable conversation transcript was captured. "
                "Continue by chat without restarting known account context."
            ),
        )

    updated_case = borrower_case_state_service.apply_delta(
        borrower_case=borrower_case,
        case_delta=result.case_delta,
        stage=Stage.RESOLUTION,
        latest_handoff_summary=result.latest_handoff_summary,
    )
    updated_case.stage = Stage.RESOLUTION
    updated_case.last_contact_channel = ContactChannel.VOICE
    updated_case.resolution_call_id = str(call.get("call_id") or borrower_case.resolution_call_id or "")
    updated_case.resolution_call_status = str(call.get("call_status") or "ended")

    for sender_type, message in transcript_turns:
        _append_message(borrower_case, Stage.RESOLUTION, sender_type, message)

    return AgentTurnActivityResult(
        borrower_case=updated_case,
        stage_result=result,
    )
