from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.domain.borrower_case import AgentTurnResult, BorrowerCase, ResolutionMode, Stage


class CollectionsWorkflowInput(BaseModel):
    borrower_id: str
    workflow_id: str
    resolution_mode: ResolutionMode = ResolutionMode.CHAT


class CollectionsWorkflowState(BaseModel):
    borrower_case: BorrowerCase
    last_agent_reply: str | None = None
    final_result: str | None = None


class BorrowerMessageWorkflowInput(BaseModel):
    message: str
    resolution_mode: ResolutionMode | None = None


class AgentPromptActivityInput(BaseModel):
    borrower_case: BorrowerCase
    instruction: str


class AgentTurnActivityInput(BaseModel):
    borrower_case: BorrowerCase
    message: str


class AgentTurnActivityResult(BaseModel):
    borrower_case: BorrowerCase
    stage_result: AgentTurnResult


class StartResolutionCallResult(BaseModel):
    call_id: str
    call_status: str | None = None


class ResolutionCallActivityInput(BaseModel):
    borrower_case: BorrowerCase
    call: dict[str, Any]


class ResolutionVoiceCallCompletedInput(BaseModel):
    call: dict[str, Any]
