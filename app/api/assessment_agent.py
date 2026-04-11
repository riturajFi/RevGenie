from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from app.agents.assessment.agent import AssessmentAgent
from app.services.chat_message import FileChatMessageService


class AssessmentAgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    borrower_id: str
    message: str


class AssessmentAgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str
    identity_verified: bool
    resolution_path: str


router = APIRouter(prefix="/agents/assessment", tags=["assessment-agent"])
chat_service = FileChatMessageService()


@router.post("", response_model=AssessmentAgentResponse)
def run_assessment_agent(payload: AssessmentAgentRequest) -> AssessmentAgentResponse:
    try:
        chat_history = chat_service.list_chat_messages_for_conversation(payload.borrower_id)
        chat_service.append_chat_message(
            user_id=payload.borrower_id,
            chat_message=payload.message,
        )
        agent = AssessmentAgent()
        result = agent.invoke(
            borrower_id=payload.borrower_id,
            message=payload.message,
            chat_history=chat_history,
        )
        chat_service.append_chat_message(
            user_id=f"agent:{payload.borrower_id}",
            chat_message=result["reply"],
        )
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return AssessmentAgentResponse(
        reply=result["reply"],
        identity_verified=False,
        resolution_path="LLM_ASSESSMENT",
    )
