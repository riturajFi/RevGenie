from __future__ import annotations

import ast
from pathlib import Path

from app.domain.lender_policy import LenderPolicy
from app.storage.lender_policy.base import LenderPolicyStorage


class PythonFileLenderPolicyStorage(LenderPolicyStorage):
    def __init__(self, file_path: str = "data/app/lender_policies.py") -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def create_lender_policy(self, lender_policy: LenderPolicy) -> LenderPolicy:
        records = self._read()
        if lender_policy.lender_id in records:
            raise ValueError(f"Lender policy already exists for {lender_policy.lender_id}")
        records[lender_policy.lender_id] = lender_policy.model_dump(mode="json")
        self._write(records)
        return lender_policy

    def get_lender_policy(self, lender_id: str) -> LenderPolicy | None:
        record = self._read().get(lender_id)
        if record is None:
            return None
        return LenderPolicy.model_validate(record)

    def list_lender_policies(self) -> list[LenderPolicy]:
        return [LenderPolicy.model_validate(record) for record in self._read().values()]

    def update_lender_policy(self, lender_id: str, lender_policy: LenderPolicy) -> LenderPolicy:
        records = self._read()
        if lender_id not in records:
            raise KeyError(f"Lender policy not found for {lender_id}")
        records[lender_policy.lender_id] = lender_policy.model_dump(mode="json")
        if lender_id != lender_policy.lender_id:
            del records[lender_id]
        self._write(records)
        return lender_policy

    def delete_lender_policy(self, lender_id: str) -> bool:
        records = self._read()
        if lender_id not in records:
            return False
        del records[lender_id]
        self._write(records)
        return True

    def _read(self) -> dict[str, dict]:
        raw = self.path.read_text(encoding="utf-8")
        if not raw.strip():
            return {}
        namespace: dict[str, object] = {}
        exec(compile(raw, str(self.path), "exec"), namespace)
        records = namespace.get("LENDER_POLICIES", {})
        if isinstance(records, dict):
            return records  # type: ignore[return-value]
        return ast.literal_eval(raw)

    def _write(self, records: dict[str, dict]) -> None:
        lines = ["LENDER_POLICIES = {"]
        for lender_id, record in sorted(records.items()):
            policy = record["policy"].replace('"""', '\\"\\"\\"')
            lines.append(f'    "{lender_id}": {{')
            lines.append(f'        "lender_id": "{record["lender_id"]}",')
            lines.append('        "policy": """')
            lines.append(policy)
            lines.append('""",')
            lines.append("    },")
        lines.append("}")
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
