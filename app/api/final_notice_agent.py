from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.final_notice.agent import FinalNoticeAgent
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_case_state import BorrowerCaseStateService


class FinalNoticeAgentRequest(BaseModel):
    borrower_id: str
    resolution_summary: str
    message: str


class FinalNoticeAgentResponse(BaseModel):
    reply: str
    stage_outcome: str
    latest_handoff_summary: str | None = None


router = APIRouter(prefix="/agents/final-notice", tags=["final-notice-agent"])
borrower_case_service = FileBorrowerCaseService()
borrower_case_state_service = BorrowerCaseStateService()


@router.post("", response_model=FinalNoticeAgentResponse)
def run_final_notice_agent(payload: FinalNoticeAgentRequest) -> FinalNoticeAgentResponse:
    try:
        borrower_case = borrower_case_service.get_borrower_case(payload.borrower_id)
        if borrower_case is None:
            raise HTTPException(status_code=404, detail="Borrower case not found")
        agent = FinalNoticeAgent()
        result = agent.invoke(
            borrower_id=payload.borrower_id,
            resolution_summary=payload.resolution_summary,
            message=payload.message,
            borrower_case=borrower_case,
        )
        updated_case = borrower_case_state_service.apply_delta(
            borrower_case=borrower_case,
            case_delta=result.case_delta,
            stage=borrower_case.stage,
            latest_handoff_summary=result.latest_handoff_summary,
        )
        borrower_case_service.update_borrower_case(payload.borrower_id, updated_case)
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return FinalNoticeAgentResponse(
        reply=result.reply,
        stage_outcome=result.stage_outcome.value,
        latest_handoff_summary=result.latest_handoff_summary,
    )
