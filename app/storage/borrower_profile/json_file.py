from __future__ import annotations

import json
from pathlib import Path

from app.domain.borrower_profile import BorrowerProfile
from app.storage.borrower_profile.base import BorrowerProfileStorage


class JsonFileBorrowerProfileStorage(BorrowerProfileStorage):
    def __init__(self, file_path: str = "data/borrower_profiles.json") -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def create_borrower_profile(self, borrower_profile: BorrowerProfile) -> BorrowerProfile:
        records = self._read()
        if borrower_profile.borrower_id in records:
            raise ValueError(f"Borrower profile already exists for {borrower_profile.borrower_id}")
        records[borrower_profile.borrower_id] = borrower_profile.model_dump(mode="json")
        self._write(records)
        return borrower_profile

    def get_borrower_profile(self, borrower_id: str) -> BorrowerProfile | None:
        record = self._read().get(borrower_id)
        if record is None:
            return None
        return BorrowerProfile.model_validate(record)

    def list_borrower_profiles(self) -> list[BorrowerProfile]:
        return [BorrowerProfile.model_validate(record) for record in self._read().values()]

    def update_borrower_profile(self, borrower_id: str, borrower_profile: BorrowerProfile) -> BorrowerProfile:
        records = self._read()
        if borrower_id not in records:
            raise KeyError(f"Borrower profile not found for {borrower_id}")
        records[borrower_profile.borrower_id] = borrower_profile.model_dump(mode="json")
        if borrower_id != borrower_profile.borrower_id:
            del records[borrower_id]
        self._write(records)
        return borrower_profile

    def delete_borrower_profile(self, borrower_id: str) -> bool:
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
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2, sort_keys=True)
