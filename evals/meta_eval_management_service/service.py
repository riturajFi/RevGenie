from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from evals.metrics_management_service.service import MetricDefinition


THIS_DIR = Path(__file__).resolve().parent
DEFAULT_META_EVAL_RUNS_PATH = THIS_DIR.parents[1] / "data" / "evals" / "meta_eval_runs.json"


class EvidenceBundle(BaseModel):
    transcript_evidence: list[str] = Field(default_factory=list)
    judgment_evidence: list[str] = Field(default_factory=list)
    policy_evidence: list[str] = Field(default_factory=list)


class ExperimentCorrectnessAnalysis(BaseModel):
    experiment_id: str
    judge_got_right: list[str] = Field(default_factory=list)
    judge_got_wrong: list[str] = Field(default_factory=list)
    judge_missed: list[str] = Field(default_factory=list)
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)


class MetaEvalMetricActionType(str, Enum):
    KEEP = "keep"
    DELETE = "delete"
    ADD = "add"
    REWRITE = "rewrite"


class MetaEvalMetricAction(BaseModel):
    action: MetaEvalMetricActionType
    metric_id: str | None = None
    metric_name: str
    rationale: str
    policy_references: list[str] = Field(default_factory=list)
    proposed_metric: MetricDefinition | None = None
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)


class MetaEvalRunRecord(BaseModel):
    run_id: str
    created_at: str
    before_experiment_id: str
    after_experiment_id: str
    metrics_key: str
    lender_id: str | None = None
    old_metrics_version: str
    correctness_analysis: list[ExperimentCorrectnessAnalysis] = Field(default_factory=list)
    metric_actions: list[MetaEvalMetricAction] = Field(default_factory=list)
    candidate_metrics: list[MetricDefinition] = Field(default_factory=list)
    metrics_diff_summary: str
    why_this_change: str
    expected_improvement: str


class MetaEvalRunStorageService(ABC):
    @abstractmethod
    def save_run(self, record: MetaEvalRunRecord) -> MetaEvalRunRecord:
        raise NotImplementedError

    @abstractmethod
    def get_run(self, run_id: str) -> MetaEvalRunRecord | None:
        raise NotImplementedError

    @abstractmethod
    def list_runs(self) -> list[MetaEvalRunRecord]:
        raise NotImplementedError


class JsonMetaEvalRunStorageService(MetaEvalRunStorageService):
    def __init__(self, path: Path = DEFAULT_META_EVAL_RUNS_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}")

    def save_run(self, record: MetaEvalRunRecord) -> MetaEvalRunRecord:
        payload = self._read_all()
        payload[record.run_id] = record.model_dump()
        self.path.write_text(json.dumps(payload, indent=2))
        return record

    def get_run(self, run_id: str) -> MetaEvalRunRecord | None:
        payload = self._read_all()
        raw = payload.get(run_id)
        if raw is None:
            return None
        return MetaEvalRunRecord.model_validate(raw)

    def list_runs(self) -> list[MetaEvalRunRecord]:
        payload = self._read_all()
        runs = [MetaEvalRunRecord.model_validate(item) for item in payload.values()]
        return sorted(runs, key=lambda item: item.created_at, reverse=True)

    def _read_all(self) -> dict:
        return json.loads(self.path.read_text())


class MetaEvalRunRecordService:
    def __init__(self, storage: MetaEvalRunStorageService | None = None) -> None:
        self.storage = storage or JsonMetaEvalRunStorageService()

    def create_run(self, **kwargs) -> MetaEvalRunRecord:
        record = MetaEvalRunRecord(
            run_id=f"meta_eval_{uuid4().hex[:12]}",
            created_at=self._utc_now(),
            **kwargs,
        )
        return self.storage.save_run(record)

    def get_run(self, run_id: str) -> MetaEvalRunRecord | None:
        return self.storage.get_run(run_id)

    def list_runs(self) -> list[MetaEvalRunRecord]:
        return self.storage.list_runs()

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
