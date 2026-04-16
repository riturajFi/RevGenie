from __future__ import annotations

from enum import Enum
from typing import Any, ClassVar, List, Optional

from pydantic import BaseModel, Field, model_validator


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


class ResolutionMode(str, Enum):
    CHAT = "CHAT"
    VOICE = "VOICE"


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


class BorrowerCaseCore(BaseModel):
    borrower_id: str
    workflow_id: str
    loan_id_masked: str
    lender_id: str
    stage: Stage
    case_status: CaseStatus
    case_type: List[str] = Field(default_factory=list)
    amount_due: int = Field(ge=0)
    identity_verified: bool = False
    next_allowed_actions: List[str] = Field(default_factory=list)
    final_disposition: Optional[str] = None


class BorrowerCase(BaseModel):
    core: BorrowerCaseCore
    attributes: dict[str, Any] = Field(default_factory=dict)
    agent_context_summary: Optional[str] = None
    latest_handoff_summary: Optional[str] = None
    latest_handoff_stage: Optional[Stage] = None

    _CORE_FIELDS: ClassVar[set[str]] = {
        "borrower_id",
        "workflow_id",
        "loan_id_masked",
        "lender_id",
        "stage",
        "case_status",
        "case_type",
        "amount_due",
        "identity_verified",
        "next_allowed_actions",
        "final_disposition",
    }
    _META_FIELDS: ClassVar[set[str]] = {
        "core",
        "attributes",
        "agent_context_summary",
        "latest_handoff_summary",
        "latest_handoff_stage",
    }

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        if "core" in data:
            normalized = dict(data)
            attributes = normalized.get("attributes", {}) or {}
            if not isinstance(attributes, dict):
                raise TypeError("BorrowerCase.attributes must be a dictionary")

            core_payload = dict(normalized.get("core", {}))
            for key in list(normalized.keys()):
                if key in cls._META_FIELDS:
                    continue
                if key in cls._CORE_FIELDS:
                    core_payload[key] = normalized.pop(key)
                elif key not in {"core", "attributes"}:
                    attributes[key] = normalized.pop(key)

            normalized["core"] = core_payload
            normalized["attributes"] = attributes
            return normalized

        working = dict(data)
        core_payload = {field: working.pop(field) for field in list(working.keys()) if field in cls._CORE_FIELDS}
        attributes = working.pop("attributes", {}) or {}
        if not isinstance(attributes, dict):
            raise TypeError("BorrowerCase.attributes must be a dictionary")

        latest_handoff_summary = working.pop("latest_handoff_summary", None)
        latest_handoff_stage = working.pop("latest_handoff_stage", None)
        agent_context_summary = working.pop("agent_context_summary", None)

        for key, value in working.items():
            if key not in cls._META_FIELDS:
                attributes[key] = value

        return {
            "core": core_payload,
            "attributes": attributes,
            "agent_context_summary": agent_context_summary,
            "latest_handoff_summary": latest_handoff_summary,
            "latest_handoff_stage": latest_handoff_stage,
        }

    @model_validator(mode="after")
    def _ensure_summary(self) -> BorrowerCase:
        if not self.agent_context_summary:
            self.agent_context_summary = self.build_agent_context_summary()
        return self

    @property
    def borrower_id(self) -> str:
        return self.core.borrower_id

    @borrower_id.setter
    def borrower_id(self, value: str) -> None:
        self.core.borrower_id = value

    @property
    def workflow_id(self) -> str:
        return self.core.workflow_id

    @workflow_id.setter
    def workflow_id(self, value: str) -> None:
        self.core.workflow_id = value

    @property
    def loan_id_masked(self) -> str:
        return self.core.loan_id_masked

    @loan_id_masked.setter
    def loan_id_masked(self, value: str) -> None:
        self.core.loan_id_masked = value

    @property
    def lender_id(self) -> str:
        return self.core.lender_id

    @lender_id.setter
    def lender_id(self, value: str) -> None:
        self.core.lender_id = value

    @property
    def stage(self) -> Stage:
        return self.core.stage

    @stage.setter
    def stage(self, value: Stage) -> None:
        self.core.stage = value

    @property
    def case_status(self) -> CaseStatus:
        return self.core.case_status

    @case_status.setter
    def case_status(self, value: CaseStatus) -> None:
        self.core.case_status = value

    @property
    def case_type(self) -> list[str]:
        return self.core.case_type

    @case_type.setter
    def case_type(self, value: list[str]) -> None:
        self.core.case_type = value

    @property
    def amount_due(self) -> int:
        return self.core.amount_due

    @amount_due.setter
    def amount_due(self, value: int) -> None:
        self.core.amount_due = value

    @property
    def identity_verified(self) -> bool:
        return self.core.identity_verified

    @identity_verified.setter
    def identity_verified(self, value: bool) -> None:
        self.core.identity_verified = value

    @property
    def next_allowed_actions(self) -> list[str]:
        return self.core.next_allowed_actions

    @next_allowed_actions.setter
    def next_allowed_actions(self, value: list[str]) -> None:
        self.core.next_allowed_actions = value

    @property
    def final_disposition(self) -> Optional[str]:
        return self.core.final_disposition

    @final_disposition.setter
    def final_disposition(self, value: Optional[str]) -> None:
        self.core.final_disposition = value

    @property
    def principal_outstanding(self) -> Optional[int]:
        return self._get_attribute("principal_outstanding")

    @principal_outstanding.setter
    def principal_outstanding(self, value: Optional[int]) -> None:
        self._set_attribute("principal_outstanding", value)

    @property
    def dpd(self) -> Optional[int]:
        return self._get_attribute("dpd")

    @dpd.setter
    def dpd(self, value: Optional[int]) -> None:
        self._set_attribute("dpd", value)

    @property
    def borrower_capacity(self) -> Optional[BorrowerCapacity]:
        return self._get_typed_attribute("borrower_capacity", BorrowerCapacity)

    @borrower_capacity.setter
    def borrower_capacity(self, value: BorrowerCapacity | dict | None) -> None:
        self._set_structured_attribute("borrower_capacity", value)

    @property
    def borrower_intent(self) -> Optional[BorrowerIntent]:
        return self._get_typed_attribute("borrower_intent", BorrowerIntent)

    @borrower_intent.setter
    def borrower_intent(self, value: BorrowerIntent | dict | None) -> None:
        self._set_structured_attribute("borrower_intent", value)

    @property
    def hardship_flags(self) -> Optional[HardshipFlags]:
        return self._get_typed_attribute("hardship_flags", HardshipFlags)

    @hardship_flags.setter
    def hardship_flags(self, value: HardshipFlags | dict | None) -> None:
        self._set_structured_attribute("hardship_flags", value)

    @property
    def dispute_flags(self) -> Optional[DisputeFlags]:
        return self._get_typed_attribute("dispute_flags", DisputeFlags)

    @dispute_flags.setter
    def dispute_flags(self, value: DisputeFlags | dict | None) -> None:
        self._set_structured_attribute("dispute_flags", value)

    @property
    def offers_made(self) -> list[str]:
        return list(self._get_attribute("offers_made", []))

    @offers_made.setter
    def offers_made(self, value: list[str]) -> None:
        self._set_attribute("offers_made", value)

    @property
    def borrower_objections(self) -> list[str]:
        return list(self._get_attribute("borrower_objections", []))

    @borrower_objections.setter
    def borrower_objections(self, value: list[str]) -> None:
        self._set_attribute("borrower_objections", value)

    @property
    def borrower_stated_position(self) -> Optional[str]:
        return self._get_attribute("borrower_stated_position")

    @borrower_stated_position.setter
    def borrower_stated_position(self, value: Optional[str]) -> None:
        self._set_attribute("borrower_stated_position", value)

    @property
    def last_deadline_offered(self) -> Optional[str]:
        return self._get_attribute("last_deadline_offered")

    @last_deadline_offered.setter
    def last_deadline_offered(self, value: Optional[str]) -> None:
        self._set_attribute("last_deadline_offered", value)

    @property
    def stop_contact_flag(self) -> bool:
        return bool(self._get_attribute("stop_contact_flag", False))

    @stop_contact_flag.setter
    def stop_contact_flag(self, value: bool) -> None:
        self._set_attribute("stop_contact_flag", value)

    @property
    def last_contact_channel(self) -> Optional[ContactChannel]:
        value = self._get_attribute("last_contact_channel")
        if value is None:
            return None
        return value if isinstance(value, ContactChannel) else ContactChannel(value)

    @last_contact_channel.setter
    def last_contact_channel(self, value: ContactChannel | str | None) -> None:
        if value is None:
            self._set_attribute("last_contact_channel", None)
            return
        normalized = value if isinstance(value, ContactChannel) else ContactChannel(value)
        self._set_attribute("last_contact_channel", normalized.value)

    @property
    def assessment_notes(self) -> Optional[str]:
        return self._get_attribute("assessment_notes")

    @assessment_notes.setter
    def assessment_notes(self, value: Optional[str]) -> None:
        self._set_attribute("assessment_notes", value)

    @property
    def resolution_notes(self) -> Optional[str]:
        return self._get_attribute("resolution_notes")

    @resolution_notes.setter
    def resolution_notes(self, value: Optional[str]) -> None:
        self._set_attribute("resolution_notes", value)

    @property
    def final_notice_notes(self) -> Optional[str]:
        return self._get_attribute("final_notice_notes")

    @final_notice_notes.setter
    def final_notice_notes(self, value: Optional[str]) -> None:
        self._set_attribute("final_notice_notes", value)

    @property
    def resolution_mode(self) -> ResolutionMode:
        value = self._get_attribute("resolution_mode")
        if value is None:
            return ResolutionMode.CHAT
        return value if isinstance(value, ResolutionMode) else ResolutionMode(value)

    @resolution_mode.setter
    def resolution_mode(self, value: ResolutionMode | str | None) -> None:
        if value is None:
            self._set_attribute("resolution_mode", None)
            return
        normalized = value if isinstance(value, ResolutionMode) else ResolutionMode(value)
        self._set_attribute("resolution_mode", normalized.value)

    @property
    def resolution_call_id(self) -> Optional[str]:
        return self._get_attribute("resolution_call_id")

    @resolution_call_id.setter
    def resolution_call_id(self, value: Optional[str]) -> None:
        self._set_attribute("resolution_call_id", value)

    @property
    def resolution_call_status(self) -> Optional[str]:
        return self._get_attribute("resolution_call_status")

    @resolution_call_status.setter
    def resolution_call_status(self, value: Optional[str]) -> None:
        self._set_attribute("resolution_call_status", value)

    def to_agent_context(self) -> dict[str, Any]:
        salient_attributes = {}
        for key in (
            "principal_outstanding",
            "dpd",
            "borrower_capacity",
            "borrower_intent",
            "hardship_flags",
            "dispute_flags",
            "stop_contact_flag",
            "borrower_stated_position",
            "offers_made",
            "borrower_objections",
            "last_deadline_offered",
            "assessment_notes",
            "resolution_notes",
            "final_notice_notes",
        ):
            value = self.attributes.get(key)
            if value not in (None, [], {}, ""):
                salient_attributes[key] = value

        return {
            "core": self.core.model_dump(mode="json"),
            "agent_context_summary": self.agent_context_summary,
            "latest_handoff_summary": self.latest_handoff_summary,
            "latest_handoff_stage": self.latest_handoff_stage.value if self.latest_handoff_stage else None,
            "salient_attributes": salient_attributes,
        }

    def build_agent_context_summary(self) -> str:
        parts: list[str] = []
        identity_text = "identity is verified" if self.identity_verified else "identity is not yet verified"
        parts.append(
            f"Borrower case for {self.lender_id} loan {self.loan_id_masked}: "
            f"{identity_text}, amount due {self.amount_due}, stage {self.stage.value}, status {self.case_status.value}."
        )

        if self.case_type:
            parts.append(f"Case type: {', '.join(self.case_type)}.")

        borrower_capacity = self.attributes.get("borrower_capacity")
        if isinstance(borrower_capacity, dict):
            capacity_bits = []
            if borrower_capacity.get("can_pay_now") is True:
                capacity_bits.append(f"can pay now up to {borrower_capacity.get('available_now', 0)}")
            elif borrower_capacity.get("can_pay_now") is False:
                capacity_bits.append("cannot pay now")
            if borrower_capacity.get("can_pay_later") is True:
                expected_date = borrower_capacity.get("expected_date")
                if expected_date:
                    capacity_bits.append(f"may pay later around {expected_date}")
                else:
                    capacity_bits.append("may pay later")
            elif borrower_capacity.get("can_pay_later") is False:
                capacity_bits.append("has not indicated a later payment date")
            if capacity_bits:
                parts.append("Capacity: " + ", ".join(capacity_bits) + ".")

        hardship_flags = self.attributes.get("hardship_flags")
        if isinstance(hardship_flags, dict):
            active_hardships = [key for key, value in hardship_flags.items() if value]
            if active_hardships:
                parts.append("Hardship signals: " + ", ".join(active_hardships) + ".")

        dispute_flags = self.attributes.get("dispute_flags")
        if isinstance(dispute_flags, dict):
            active_disputes = [key for key, value in dispute_flags.items() if value]
            if active_disputes:
                parts.append("Dispute signals: " + ", ".join(active_disputes) + ".")

        if self.stop_contact_flag:
            parts.append("Stop-contact flag is present.")

        borrower_position = self.borrower_stated_position
        if borrower_position:
            parts.append(f"Borrower stated position: {borrower_position}")

        if self.next_allowed_actions:
            parts.append("Next allowed actions: " + ", ".join(self.next_allowed_actions) + ".")

        return " ".join(parts)

    def _get_attribute(self, key: str, default: Any = None) -> Any:
        return self.attributes.get(key, default)

    def _set_attribute(self, key: str, value: Any) -> None:
        if value is None:
            self.attributes.pop(key, None)
            return
        self.attributes[key] = value

    def _get_typed_attribute(self, key: str, model_cls: type[BaseModel]) -> Any:
        value = self.attributes.get(key)
        if value is None:
            return None
        if isinstance(value, model_cls):
            return value
        return model_cls.model_validate(value)

    def _set_structured_attribute(self, key: str, value: BaseModel | dict | None) -> None:
        if value is None:
            self.attributes.pop(key, None)
            return
        if isinstance(value, BaseModel):
            self.attributes[key] = value.model_dump(mode="python")
            return
        self.attributes[key] = value


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
