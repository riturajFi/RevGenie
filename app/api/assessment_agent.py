from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.assessment.agent import AssessmentAgent
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_case_state import BorrowerCaseStateService
from app.services.chat_message import FileChatMessageService


class AssessmentAgentRequest(BaseModel):
    borrower_id: str
    message: str


class AssessmentAgentResponse(BaseModel):
    reply: str
    identity_verified: bool
    stage_outcome: str
    latest_handoff_summary: str | None = None


router = APIRouter(prefix="/agents/assessment", tags=["assessment-agent"])
chat_service = FileChatMessageService()
borrower_case_service = FileBorrowerCaseService()
borrower_case_state_service = BorrowerCaseStateService()


@router.post("", response_model=AssessmentAgentResponse)
def run_assessment_agent(payload: AssessmentAgentRequest) -> AssessmentAgentResponse:
    try:
        borrower_case = borrower_case_service.get_borrower_case(payload.borrower_id)
        if borrower_case is None:
            raise HTTPException(status_code=404, detail="Borrower case not found")
        chat_history = chat_service.list_chat_messages_for_conversation(payload.borrower_id)
        chat_service.append_chat_message(
            user_id=payload.borrower_id,
            chat_message=payload.message,
        )
        agent = AssessmentAgent()
        result = agent.invoke(
            borrower_id=payload.borrower_id,
            message=payload.message,
            borrower_case=borrower_case,
            chat_history=chat_history,
        )
        updated_case = borrower_case_state_service.apply_delta(
            borrower_case=borrower_case,
            case_delta=result.case_delta,
            stage=borrower_case.stage,
            latest_handoff_summary=result.latest_handoff_summary,
        )
        borrower_case_service.update_borrower_case(payload.borrower_id, updated_case)
        chat_service.append_chat_message(
            user_id=f"agent:{payload.borrower_id}",
            chat_message=result.reply,
        )
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return AssessmentAgentResponse(
        reply=result.reply,
        identity_verified=updated_case.identity_verified,
        stage_outcome=result.stage_outcome.value,
        latest_handoff_summary=result.latest_handoff_summary,
    )
