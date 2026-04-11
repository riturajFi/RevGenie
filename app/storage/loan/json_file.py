from __future__ import annotations

import json
from pathlib import Path

from app.domain.loan import Loan
from app.storage.loan.base import LoanStorage


class JsonFileLoanStorage(LoanStorage):
    def __init__(self, file_path: str = "data/loans.json") -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def create_loan(self, loan: Loan) -> Loan:
        records = self._read()
        if loan.account_id in records:
            raise ValueError(f"Loan already exists for {loan.account_id}")
        records[loan.account_id] = loan.model_dump(mode="json")
        self._write(records)
        return loan

    def get_loan(self, account_id: str) -> Loan | None:
        record = self._read().get(account_id)
        if record is None:
            return None
        return Loan.model_validate(record)

    def list_loans(self) -> list[Loan]:
        return [Loan.model_validate(record) for record in self._read().values()]

    def update_loan(self, account_id: str, loan: Loan) -> Loan:
        records = self._read()
        if account_id not in records:
            raise KeyError(f"Loan not found for {account_id}")
        records[loan.account_id] = loan.model_dump(mode="json")
        if account_id != loan.account_id:
            del records[account_id]
        self._write(records)
        return loan

    def delete_loan(self, account_id: str) -> bool:
        records = self._read()
        if account_id not in records:
            return False
        del records[account_id]
        self._write(records)
        return True

    def _read(self) -> dict[str, dict]:
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write(self, records: dict[str, dict]) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2, sort_keys=True)
