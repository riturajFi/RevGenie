from __future__ import annotations

import json
from pathlib import Path

from app.domain.lender_profile import LenderProfile
from app.storage.lender_profile.base import LenderProfileStorage


class JsonFileLenderProfileStorage(LenderProfileStorage):
    def __init__(self, file_path: str = "data/app/lender_profiles.json") -> None:
        self.path = Path(file_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def create_lender_profile(self, lender_profile: LenderProfile) -> LenderProfile:
        records = self._read()
        if lender_profile.lender_id in records:
            raise ValueError(f"Lender profile already exists for {lender_profile.lender_id}")
        records[lender_profile.lender_id] = lender_profile.model_dump(mode="json")
        self._write(records)
        return lender_profile

    def get_lender_profile(self, lender_id: str) -> LenderProfile | None:
        record = self._read().get(lender_id)
        if record is None:
            return None
        return LenderProfile.model_validate(record)

    def list_lender_profiles(self) -> list[LenderProfile]:
        return [LenderProfile.model_validate(record) for record in self._read().values()]

    def update_lender_profile(self, lender_id: str, lender_profile: LenderProfile) -> LenderProfile:
        records = self._read()
        if lender_id not in records:
            raise KeyError(f"Lender profile not found for {lender_id}")
        records[lender_profile.lender_id] = lender_profile.model_dump(mode="json")
        if lender_id != lender_profile.lender_id:
            del records[lender_id]
        self._write(records)
        return lender_profile

    def delete_lender_profile(self, lender_id: str) -> bool:
        records = self._read()
        if lender_id not in records:
            return False
        del records[lender_id]
        self._write(records)
        return True

    def _read(self) -> dict[str, dict]:
        with self.path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write(self, records: dict[str, dict]) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2, sort_keys=True)
