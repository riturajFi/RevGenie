from __future__ import annotations

import json
from uuid import uuid4
from pathlib import Path

from app.domain.borrower_case import BorrowerCase
from app.storage.borrower_case.base import BorrowerCaseStorage


class JsonFileBorrowerCaseStorage(BorrowerCaseStorage):
    def __init__(self, file_path: str = "data/app/borrower_cases.json") -> None:
        self.path = Path(file_path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def create_borrower_case(self, borrower_case: BorrowerCase) -> BorrowerCase:
        records = self._read()
        if borrower_case.borrower_id in records:
            raise ValueError(f"Borrower case already exists for {borrower_case.borrower_id}")

        records[borrower_case.borrower_id] = borrower_case.model_dump(mode="json")
        self._write(records)
        return borrower_case

    def get_borrower_case(self, borrower_id: str) -> BorrowerCase | None:
        record = self._read().get(borrower_id)
        if record is None:
            return None
        return BorrowerCase.model_validate(record)

    def list_borrower_cases(self) -> list[BorrowerCase]:
        return [BorrowerCase.model_validate(record) for record in self._read().values()]

    def update_borrower_case(self, borrower_id: str, borrower_case: BorrowerCase) -> BorrowerCase:
        records = self._read()
        if borrower_id not in records:
            raise KeyError(f"Borrower case not found for {borrower_id}")

        records[borrower_case.borrower_id] = borrower_case.model_dump(mode="json")
        if borrower_id != borrower_case.borrower_id:
            del records[borrower_id]

        self._write(records)
        return borrower_case

    def delete_borrower_case(self, borrower_id: str) -> bool:
        records = self._read()
        if borrower_id not in records:
            return False

        del records[borrower_id]
        self._write(records)
        return True

    def _read(self) -> dict[str, dict]:
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write(self, records: dict[str, dict]) -> None:
        temp_path = self.path.with_name(f"{self.path.name}.{uuid4().hex}.tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2, sort_keys=True)
        temp_path.replace(self.path)
