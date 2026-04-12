from __future__ import annotations

from pydantic import BaseModel

from app.domain.borrower_case import AgentTurnResult, BorrowerCase, Stage


class CollectionsWorkflowInput(BaseModel):
    borrower_id: str
    workflow_id: str


class CollectionsWorkflowState(BaseModel):
    borrower_case: BorrowerCase
    last_agent_reply: str | None = None
    final_result: str | None = None


class AgentPromptActivityInput(BaseModel):
    borrower_case: BorrowerCase
    instruction: str


class AgentTurnActivityInput(BaseModel):
    borrower_case: BorrowerCase
    message: str


class AgentTurnActivityResult(BaseModel):
    borrower_case: BorrowerCase
    stage_result: AgentTurnResult
