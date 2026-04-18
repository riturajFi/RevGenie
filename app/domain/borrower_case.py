from __future__ import annotations

from enum import Enum
from typing import Any, ClassVar, Optional

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


class ResolutionMode(str, Enum):
    CHAT = "CHAT"
    VOICE = "VOICE"


class BorrowerCaseCore(BaseModel):
    borrower_id: str
    workflow_id: str
    loan_id_masked: str
    lender_id: str
    stage: Stage
    case_status: CaseStatus
    amount_due: int = Field(ge=0)
    final_disposition: Optional[str] = None


class BorrowerCase(BaseModel):
    core: BorrowerCaseCore
    attributes: dict[str, Any] = Field(default_factory=dict)
    latest_handoff_summary: Optional[str] = None

    _CORE_FIELDS: ClassVar[set[str]] = {
        "borrower_id",
        "workflow_id",
        "loan_id_masked",
        "lender_id",
        "stage",
        "case_status",
        "amount_due",
        "final_disposition",
    }
    _META_FIELDS: ClassVar[set[str]] = {
        "core",
        "attributes",
        "latest_handoff_summary",
    }
    _ALLOWED_ATTRIBUTES: ClassVar[set[str]] = {
        "resolution_mode",
        "resolution_call_id",
        "resolution_call_status",
        "prompt_version_overrides",
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

        for key, value in working.items():
            if key not in cls._META_FIELDS:
                attributes[key] = value

        return {
            "core": core_payload,
            "attributes": attributes,
            "latest_handoff_summary": latest_handoff_summary,
        }

    @model_validator(mode="after")
    def _prune_attributes(self) -> BorrowerCase:
        self.attributes = {
            key: value
            for key, value in self.attributes.items()
            if key in self._ALLOWED_ATTRIBUTES and value not in (None, "", [], {})
        }
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
    def amount_due(self) -> int:
        return self.core.amount_due

    @amount_due.setter
    def amount_due(self, value: int) -> None:
        self.core.amount_due = value

    @property
    def final_disposition(self) -> Optional[str]:
        return self.core.final_disposition

    @final_disposition.setter
    def final_disposition(self, value: Optional[str]) -> None:
        self.core.final_disposition = value

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

    @property
    def prompt_version_overrides(self) -> dict[str, str]:
        value = self._get_attribute("prompt_version_overrides")
        if not isinstance(value, dict):
            return {}
        return {
            str(agent_id): str(version_id)
            for agent_id, version_id in value.items()
            if str(agent_id).strip() and str(version_id).strip()
        }

    @prompt_version_overrides.setter
    def prompt_version_overrides(self, value: dict[str, str] | None) -> None:
        if not value:
            self._set_attribute("prompt_version_overrides", None)
            return
        normalized = {
            str(agent_id): str(version_id)
            for agent_id, version_id in value.items()
            if str(agent_id).strip() and str(version_id).strip()
        }
        self._set_attribute("prompt_version_overrides", normalized or None)

    def prompt_version_for(self, agent_id: str) -> str | None:
        return self.prompt_version_overrides.get(agent_id)

    def to_agent_context(self) -> dict[str, Any]:
        salient_attributes = {}
        resolution_mode = self.attributes.get("resolution_mode")
        if resolution_mode not in (None, ""):
            salient_attributes["resolution_mode"] = resolution_mode
        prompt_version_overrides = self.prompt_version_overrides
        if prompt_version_overrides:
            salient_attributes["prompt_version_overrides"] = prompt_version_overrides
        return {
            "core": self.core.model_dump(mode="json"),
            "latest_handoff_summary": self.latest_handoff_summary,
            "salient_attributes": salient_attributes,
        }

    def _get_attribute(self, key: str, default: Any = None) -> Any:
        return self.attributes.get(key, default)

    def _set_attribute(self, key: str, value: Any) -> None:
        if value is None:
            self.attributes.pop(key, None)
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
