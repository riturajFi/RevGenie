from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.agents.resolution.agent import ResolutionAgent


class ResolutionAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    borrower_id: str
    assessment_summary: str
    message: str


class ResolutionAgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str


router = APIRouter(prefix="/agents/resolution", tags=["resolution-agent"])


@router.post("", response_model=ResolutionAgentResponse)
def run_resolution_agent(payload: ResolutionAgentRequest) -> ResolutionAgentResponse:
    try:
        agent = ResolutionAgent()
        result = agent.invoke(
            borrower_id=payload.borrower_id,
            assessment_summary=payload.assessment_summary,
            message=payload.message,
        )
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return ResolutionAgentResponse(reply=result["reply"])
