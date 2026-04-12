from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domain.borrower_case import BorrowerCase, Stage


class BorrowerCaseStateService:
    def apply_delta(
        self,
        borrower_case: BorrowerCase,
        case_delta: dict[str, Any],
        stage: Stage,
        latest_handoff_summary: str | None = None,
    ) -> BorrowerCase:
        case_data = deepcopy(borrower_case.model_dump(mode="python"))

        for field_path, value in case_delta.items():
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
        current[parts[-1]] = value
