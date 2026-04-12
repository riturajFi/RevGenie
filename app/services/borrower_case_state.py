from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domain.borrower_case import BorrowerCase, Stage


class BorrowerCaseStateService:
    BLOCKED_FIELDS = {
        "workflow_id",
        "lender_id",
        "amount_due",
        "principal_outstanding",
        "dpd",
        "stage",
        "case_status",
        "final_disposition",
        "last_contact_channel",
    }

    def apply_delta(
        self,
        borrower_case: BorrowerCase,
        case_delta: dict[str, Any],
        stage: Stage,
        latest_handoff_summary: str | None = None,
    ) -> BorrowerCase:
        case_data = deepcopy(borrower_case.model_dump(mode="python"))

        for field_path, value in case_delta.items():
            root_field = field_path.split(".")[0]
            if field_path in self.BLOCKED_FIELDS or root_field in self.BLOCKED_FIELDS:
                continue
            self._set_path(case_data, field_path, value)

        if latest_handoff_summary:
            case_data["latest_handoff_summary"] = latest_handoff_summary
            case_data["latest_handoff_stage"] = stage.value

        return BorrowerCase.model_validate(case_data)

    def _set_path(self, root: dict[str, Any], field_path: str, value: Any) -> None:
        current = root
        parts = field_path.split(".")
        for part in parts[:-1]:
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
