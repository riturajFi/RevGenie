from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.agents.final_notice.agent import FinalNoticeAgent


class FinalNoticeAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    borrower_id: str
    resolution_summary: str
    message: str


class FinalNoticeAgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str


router = APIRouter(prefix="/agents/final-notice", tags=["final-notice-agent"])


@router.post("", response_model=FinalNoticeAgentResponse)
def run_final_notice_agent(payload: FinalNoticeAgentRequest) -> FinalNoticeAgentResponse:
    try:
        agent = FinalNoticeAgent()
        result = agent.invoke(
            borrower_id=payload.borrower_id,
            resolution_summary=payload.resolution_summary,
            message=payload.message,
        )
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return FinalNoticeAgentResponse(reply=result["reply"])
