from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domain.borrower_case import BorrowerCase, Stage


class BorrowerCaseStateService:
    BLOCKED_FIELDS = {
        "core.borrower_id",
        "core.workflow_id",
        "core.loan_id_masked",
        "core.lender_id",
        "core.stage",
        "core.case_status",
        "core.amount_due",
        "core.final_disposition",
        "attributes.last_contact_channel",
    }
    LEGACY_CORE_FIELDS = {
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
    META_FIELDS = {"agent_context_summary", "latest_handoff_summary", "latest_handoff_stage"}

    def apply_delta(
        self,
        borrower_case: BorrowerCase,
        case_delta: dict[str, Any],
        stage: Stage,
        latest_handoff_summary: str | None = None,
    ) -> BorrowerCase:
        case_data = deepcopy(borrower_case.model_dump(mode="python"))

        for field_path, value in case_delta.items():
            normalized_field_path = self._normalize_field_path(field_path)
            root_field = normalized_field_path.split(".")[0]
            if normalized_field_path in self.BLOCKED_FIELDS or root_field in self.BLOCKED_FIELDS:
                continue
            self._set_path(case_data, normalized_field_path, value)

        if latest_handoff_summary:
            case_data["latest_handoff_summary"] = latest_handoff_summary
            case_data["latest_handoff_stage"] = stage.value

        if "agent_context_summary" not in case_delta:
            case_data["agent_context_summary"] = None

        return BorrowerCase.model_validate(case_data)

    def _normalize_field_path(self, field_path: str) -> str:
        if field_path in self.META_FIELDS:
            return field_path
        if field_path.startswith("core.") or field_path.startswith("attributes."):
            return field_path
        if field_path.startswith("salient_attributes."):
            return field_path.replace("salient_attributes.", "attributes.", 1)
        if field_path == "salient_attributes":
            return "attributes"

        root_field = field_path.split(".")[0]
        if root_field in self.LEGACY_CORE_FIELDS:
            return f"core.{field_path}"
        return f"attributes.{field_path}"

    def _set_path(self, root: dict[str, Any], field_path: str, value: Any) -> None:
        current = root
        parts = field_path.split(".")
        for part in parts[:-1]:
            if part not in current or current[part] is None:
                current[part] = {}
            current = current[part]
        existing_value = current.get(parts[-1])
        if isinstance(existing_value, dict) and isinstance(value, dict):
            current[parts[-1]] = self._merge_dict(existing_value, value)
            return
        current[parts[-1]] = value

    def _merge_dict(self, existing: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(existing)
        for key, value in update.items():
            if isinstance(merged.get(key), dict) and isinstance(value, dict):
                merged[key] = self._merge_dict(merged[key], value)
            else:
                merged[key] = value
        return merged
