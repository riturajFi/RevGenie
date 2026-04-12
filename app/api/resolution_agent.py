from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.resolution.agent import ResolutionAgent
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_case_state import BorrowerCaseStateService


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


@router.post("", response_model=ResolutionAgentResponse)
def run_resolution_agent(payload: ResolutionAgentRequest) -> ResolutionAgentResponse:
    try:
        borrower_case = borrower_case_service.get_borrower_case(payload.borrower_id)
        if borrower_case is None:
            raise HTTPException(status_code=404, detail="Borrower case not found")
        agent = ResolutionAgent()
        result = agent.invoke(
            borrower_id=payload.borrower_id,
            assessment_summary=payload.assessment_summary,
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

    return ResolutionAgentResponse(
        reply=result.reply,
        stage_outcome=result.stage_outcome.value,
        latest_handoff_summary=result.latest_handoff_summary,
    )
