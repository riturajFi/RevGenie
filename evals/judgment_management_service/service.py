from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


THIS_DIR = Path(__file__).resolve().parent
DEFAULT_JUDGMENT_RECORDS_PATH = THIS_DIR.parents[1] / "data" / "evals" / "judgment_records.json"


class StoredJudgeScore(BaseModel):
    metric_id: str
    name: str
    score: float
    reason: str


class StoredJudgeResult(BaseModel):
    experiment_id: str
    scores: dict[str, StoredJudgeScore]
    overall_score: float
    verdict: str


class PromptBenchmarkThresholds(BaseModel):
    required_mean_score_delta: float
    required_win_rate: float
    require_compliance_non_regression: bool


class PromptBenchmarkScenarioResult(BaseModel):
    scenario_id: str
    borrower_id: str
    lender_id: str
    baseline_experiment_id: str
    candidate_experiment_id: str
    baseline_score: float
    candidate_score: float
    baseline_verdict: str
    candidate_verdict: str
    baseline_compliance_score: float
    candidate_compliance_score: float
    compliance_delta: float
    winner: str


class PromptBenchmarkSummary(BaseModel):
    decision: str
    reason: str
    scenario_ids: list[str]
    thresholds: PromptBenchmarkThresholds
    baseline_mean_score: float
    candidate_mean_score: float
    mean_score_delta: float
    baseline_pass_rate: float
    candidate_pass_rate: float
    candidate_win_rate: float
    baseline_mean_compliance_score: float
    candidate_mean_compliance_score: float
    compliance_non_regression: bool
    scenario_results: list[PromptBenchmarkScenarioResult] = Field(default_factory=list)


class PromptChangeProposal(BaseModel):
    agent_id: str
    old_version_id: str
    new_version_id: str
    diff_summary: str
    why_this_change: str | None = None
    activation_status: str
    benchmark_result: PromptBenchmarkSummary | None = None


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
