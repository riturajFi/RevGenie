from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel


THIS_DIR = Path(__file__).resolve().parent
DEFAULT_COMPANY_POLICY_PATH = THIS_DIR.parent / "data" / "meta_eval_company_policy.json"
DEFAULT_COMPANY_POLICY_TEXT = (
    "Replace this text with the company collections policy used by the meta evaluator. "
    "This policy should define what good judging looks like, which compliance expectations matter, "
    "and what kinds of evaluator metrics should exist, be removed, or be rewritten."
)


class CompanyPolicy(BaseModel):
    policy_text: str
    updated_at: str


class CompanyPolicyManager:
    def __init__(self, path: Path = DEFAULT_COMPANY_POLICY_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_policy(
                CompanyPolicy(
                    policy_text=DEFAULT_COMPANY_POLICY_TEXT,
                    updated_at=self._utc_now(),
                )
            )

    def get_policy(self) -> CompanyPolicy:
        return CompanyPolicy.model_validate(json.loads(self.path.read_text()))

    def set_policy(self, policy_text: str) -> CompanyPolicy:
        policy = CompanyPolicy(
            policy_text=policy_text.strip(),
            updated_at=self._utc_now(),
        )
        self._write_policy(policy)
        return policy

    def _write_policy(self, policy: CompanyPolicy) -> None:
        self.path.write_text(json.dumps(policy.model_dump(), indent=2))

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
