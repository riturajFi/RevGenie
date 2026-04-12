from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.resolution.agent import ResolutionAgent
from app.domain.borrower_case import Stage
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_case_state import BorrowerCaseStateService
from app.services.chat_message import get_chat_message_service


class ResolutionAgentRequest(BaseModel):
    borrower_id: str
    assessment_summary: str
    message: str


class ResolutionAgentResponse(BaseModel):
    reply: str
    stage_outcome: str
    latest_handoff_summary: str | None = None


router = APIRouter(prefix="/agents/resolution", tags=["resolution-agent"])
borrower_case_service = FileBorrowerCaseService()
borrower_case_state_service = BorrowerCaseStateService()
chat_service = get_chat_message_service()


@router.post("", response_model=ResolutionAgentResponse)
def run_resolution_agent(payload: ResolutionAgentRequest) -> ResolutionAgentResponse:
    try:
        borrower_case = borrower_case_service.get_borrower_case(payload.borrower_id)
        if borrower_case is None:
            raise HTTPException(status_code=404, detail="Borrower case not found")
        chat_service.append_handoff_message(
            user_id=payload.borrower_id,
            agent_id=Stage.RESOLUTION.value,
            summary=payload.assessment_summary,
        )
        chat_history = chat_service.list_messages(payload.borrower_id, Stage.RESOLUTION.value)
        chat_service.append_message(
            user_id=payload.borrower_id,
            agent_id=Stage.RESOLUTION.value,
            sender_type="borrower",
            message=payload.message,
        )
        agent = ResolutionAgent()
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
        chat_service.append_message(
            user_id=payload.borrower_id,
            agent_id=Stage.RESOLUTION.value,
            sender_type="agent",
            message=result.reply,
        )
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return ResolutionAgentResponse(
        reply=result.reply,
        stage_outcome=result.stage_outcome.value,
        latest_handoff_summary=result.latest_handoff_summary,
    )
