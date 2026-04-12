from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class Stage(str, Enum):
    ASSESSMENT = "ASSESSMENT"
    RESOLUTION = "RESOLUTION"
    FINAL_NOTICE = "FINAL_NOTICE"


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    STOP_CONTACT = "STOP_CONTACT"


class ContactChannel(str, Enum):
    CHAT = "CHAT"
    VOICE = "VOICE"
    SMS = "SMS"
    EMAIL = "EMAIL"


class BorrowerCapacity(BaseModel):
    can_pay_now: bool
    available_now: int = Field(ge=0)
    can_pay_later: bool
    expected_date: Optional[str] = None


class BorrowerIntent(BaseModel):
    wants_settlement: bool
    wants_full_closure: bool
    protect_cibil: bool


class HardshipFlags(BaseModel):
    job_loss: bool
    medical_issue: bool
    student: bool
    emotional_distress: bool


class DisputeFlags(BaseModel):
    claims_paid: bool
    claims_wrong_commitment: bool


class ApprovalState(BaseModel):
    required: bool
    type: Optional[str] = None
    status: Optional[str] = None


class BorrowerCase(BaseModel):
    borrower_id: str
    workflow_id: str
    loan_id_masked: str
    lender_id: str
    stage: Stage
    case_status: CaseStatus
    case_type: List[str]
    amount_due: int = Field(ge=0)
    principal_outstanding: int = Field(ge=0)
    dpd: int = Field(ge=0)
    borrower_capacity: BorrowerCapacity
    borrower_intent: BorrowerIntent
    hardship_flags: HardshipFlags
    dispute_flags: DisputeFlags
    approval_state: ApprovalState
    offers_made: List[str] = Field(default_factory=list)
    borrower_objections: List[str] = Field(default_factory=list)
    borrower_stated_position: Optional[str] = None
    last_deadline_offered: Optional[str] = None
    next_allowed_actions: List[str] = Field(default_factory=list)
    stop_contact_flag: bool
    identity_verified: bool
    last_contact_channel: ContactChannel
    assessment_notes: Optional[str] = None
    resolution_notes: Optional[str] = None
    final_notice_notes: Optional[str] = None
    latest_handoff_summary: Optional[str] = None
    latest_handoff_stage: Optional[Stage] = None
    final_disposition: Optional[str] = None


class AgentStageOutcome(str, Enum):
    CONTINUE = "CONTINUE"
    ASSESSMENT_COMPLETE = "ASSESSMENT_COMPLETE"
    DEAL_AGREED = "DEAL_AGREED"
    NO_DEAL = "NO_DEAL"
    RESOLVED = "RESOLVED"
    NO_RESOLUTION = "NO_RESOLUTION"


class AgentTurnResult(BaseModel):
    reply: str
    stage_outcome: AgentStageOutcome
    case_delta: dict[str, Any] = Field(default_factory=dict)
    latest_handoff_summary: Optional[str] = None
