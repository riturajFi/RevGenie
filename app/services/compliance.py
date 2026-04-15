from __future__ import annotations

import json
from pathlib import Path


DEFAULT_COMPLIANCE_PATH = (
    Path(__file__).resolve().parents[2]
    / "experiment-harness"
    / "llm_v0"
    / "data"
    / "compliance_rules.json"
)


class FileComplianceService:
    def __init__(self, file_path: Path = DEFAULT_COMPLIANCE_PATH) -> None:
        self.file_path = file_path

    def get_rules_text(self) -> str:
        if not self.file_path.exists():
            return ""
        payload = json.loads(self.file_path.read_text())
        return payload.get("rules_text", "")
