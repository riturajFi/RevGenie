from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.borrower_case import AgentTurnResult, BorrowerCase, Stage


class CollectionsWorkflowInput(BaseModel):
    borrower_id: str
    workflow_id: str
    response_timeout_seconds: int = 60


class CollectionsWorkflowState(BaseModel):
    borrower_case: BorrowerCase
    assessment_no_response_attempts: int = 0
    last_agent_reply: str | None = None
    final_result: str | None = None
    pending_messages: list[str] = Field(default_factory=list)


class AgentPromptActivityInput(BaseModel):
    borrower_case: BorrowerCase
    instruction: str


class AgentTurnActivityInput(BaseModel):
    borrower_case: BorrowerCase
    message: str


class AgentTurnActivityResult(BaseModel):
    borrower_case: BorrowerCase
    stage_result: AgentTurnResult
