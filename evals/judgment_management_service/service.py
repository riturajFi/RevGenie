from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel


THIS_DIR = Path(__file__).resolve().parent
DEFAULT_JUDGMENT_RECORDS_PATH = THIS_DIR.parents[1] / "data" / "evals" / "judgment_records.json"


class StoredJudgeScore(BaseModel):
    metric_id: str
    name: str
    score: float
    reason: str


class StoredJudgeResult(BaseModel):
    experiment_id: str
    scores: list[StoredJudgeScore]
    overall_score: float
    verdict: str


class PromptChangeProposal(BaseModel):
    agent_id: str
    old_version_id: str
    new_version_id: str
    diff_summary: str
    why_this_change: str | None = None
    activation_status: str


class JudgmentRecord(BaseModel):
    experiment_id: str
    judgment: StoredJudgeResult | None = None
    prompt_change: PromptChangeProposal | None = None
    updated_at: str


class JudgmentStorageService(ABC):
    @abstractmethod
    def save_judgment(self, record: JudgmentRecord) -> JudgmentRecord:
        raise NotImplementedError

    @abstractmethod
    def get_judgment(self, experiment_id: str) -> JudgmentRecord | None:
        raise NotImplementedError

    @abstractmethod
    def list_judgments(self) -> list[JudgmentRecord]:
        raise NotImplementedError


class JsonJudgmentStorageService(JudgmentStorageService):
    def __init__(self, path: Path = DEFAULT_JUDGMENT_RECORDS_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}")

    def save_judgment(self, record: JudgmentRecord) -> JudgmentRecord:
        payload = self._read_all()
        payload[record.experiment_id] = record.model_dump()
        self.path.write_text(json.dumps(payload, indent=2))
        return record

    def get_judgment(self, experiment_id: str) -> JudgmentRecord | None:
        payload = self._read_all()
        record = payload.get(experiment_id)
        if record is None:
            return None
        return JudgmentRecord.model_validate(record)

    def list_judgments(self) -> list[JudgmentRecord]:
        payload = self._read_all()
        records = [JudgmentRecord.model_validate(item) for item in payload.values()]
        return sorted(records, key=lambda item: item.updated_at)

    def _read_all(self) -> dict:
        return json.loads(self.path.read_text())


class JudgmentRecordService:
    def __init__(self, storage: JudgmentStorageService | None = None) -> None:
        self.storage = storage or JsonJudgmentStorageService()

    def save_judgment_result(self, judgment_result) -> JudgmentRecord:
        existing = self.storage.get_judgment(judgment_result.experiment_id)
        record = JudgmentRecord(
            experiment_id=judgment_result.experiment_id,
            judgment=StoredJudgeResult.model_validate(judgment_result.model_dump()),
            prompt_change=existing.prompt_change if existing else None,
            updated_at=self._utc_now(),
        )
        return self.storage.save_judgment(record)

    def save_prompt_change(self, experiment_id: str, prompt_change_result) -> JudgmentRecord:
        existing = self.storage.get_judgment(experiment_id)
        record = JudgmentRecord(
            experiment_id=experiment_id,
            judgment=existing.judgment if existing else None,
            prompt_change=PromptChangeProposal.model_validate(prompt_change_result.model_dump()),
            updated_at=self._utc_now(),
        )
        return self.storage.save_judgment(record)

    def get_record(self, experiment_id: str) -> JudgmentRecord | None:
        return self.storage.get_judgment(experiment_id)

    def list_records(self) -> list[JudgmentRecord]:
        return self.storage.list_judgments()

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
