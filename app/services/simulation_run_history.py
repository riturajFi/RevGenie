from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field


STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "evals" / "simulation_runs.json"


class SimulationEvaluationRecord(BaseModel):
    evaluation_id: str
    created_at: str
    metrics_key: str
    lender_id: str | None = None
    overall_score: float
    verdict: str
    prompt_versions: dict[str, str] = Field(default_factory=dict)


class SimulationRunRecord(BaseModel):
    run_id: str
    workflow_id: str
    experiment_id: str
    borrower_id: str
    scenario_id: str
    status: str
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    evaluations: list[SimulationEvaluationRecord] = Field(default_factory=list)


class SimulationRunHistoryService:
    def __init__(self, path: Path = STORE_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}")

    def create_run(
        self,
        *,
        run_id: str,
        workflow_id: str,
        experiment_id: str,
        borrower_id: str,
        scenario_id: str,
        status: str,
        started_at: str,
    ) -> SimulationRunRecord:
        record = SimulationRunRecord(
            run_id=run_id,
            workflow_id=workflow_id,
            experiment_id=experiment_id,
            borrower_id=borrower_id,
            scenario_id=scenario_id,
            status=status,
            started_at=started_at,
        )
        payload = self._read_all()
        payload[run_id] = record.model_dump()
        self._write_all(payload)
        return record

    def update_status(
        self,
        *,
        run_id: str,
        status: str,
        finished_at: str | None = None,
        error: str | None = None,
    ) -> SimulationRunRecord | None:
        payload = self._read_all()
        raw = payload.get(run_id)
        if raw is None:
            return None
        record = SimulationRunRecord.model_validate(raw)
        record.status = status
        record.finished_at = finished_at
        record.error = error
        payload[run_id] = record.model_dump()
        self._write_all(payload)
        return record

    def append_evaluation(
        self,
        *,
        run_id: str,
        metrics_key: str,
        lender_id: str | None,
        overall_score: float,
        verdict: str,
        prompt_versions: dict[str, str] | None = None,
    ) -> SimulationRunRecord | None:
        payload = self._read_all()
        raw = payload.get(run_id)
        if raw is None:
            return None
        record = SimulationRunRecord.model_validate(raw)
        evaluation = SimulationEvaluationRecord(
            evaluation_id=f"eval_{uuid4().hex[:10]}",
            created_at=self._utc_now(),
            metrics_key=metrics_key,
            lender_id=lender_id,
            overall_score=overall_score,
            verdict=verdict,
            prompt_versions=prompt_versions or {},
        )
        record.evaluations.append(evaluation)
        payload[run_id] = record.model_dump()
        self._write_all(payload)
        return record

    def list_runs(self) -> list[SimulationRunRecord]:
        payload = self._read_all()
        records = [SimulationRunRecord.model_validate(item) for item in payload.values()]
        return sorted(records, key=lambda item: item.started_at)

    def get_run(self, run_id: str) -> SimulationRunRecord | None:
        payload = self._read_all()
        raw = payload.get(run_id)
        if raw is None:
            return None
        return SimulationRunRecord.model_validate(raw)

    def _read_all(self) -> dict:
        return json.loads(self.path.read_text())

    def _write_all(self, payload: dict) -> None:
        self.path.write_text(json.dumps(payload, indent=2))

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
