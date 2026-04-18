from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


THIS_DIR = Path(__file__).resolve().parent
DEFAULT_EVAL_CONFIG_PATH = THIS_DIR.parents[1] / "data" / "evals" / "evaluation_config.json"


class EvaluationConfig(BaseModel):
    version_id: str
    benchmark_scenario_ids: list[str] = Field(default_factory=list)
    benchmark_max_turns: int = 24
    required_mean_score_delta: float = 0.25
    required_win_rate: float = 0.5
    require_compliance_non_regression: bool = True
    diff_summary: str | None = None
    created_at: str


class EvaluationConfigState(BaseModel):
    active_version_id: str
    versions: list[EvaluationConfig] = Field(default_factory=list)


class EvaluationConfigService:
    def __init__(self, path: Path = DEFAULT_EVAL_CONFIG_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_state(self._seed_state())

    def get_active(self) -> EvaluationConfig:
        state = self._read_state()
        for version in state.versions:
            if version.version_id == state.active_version_id:
                return version
        raise KeyError("Active evaluation config not found")

    def get_version(self, version_id: str) -> EvaluationConfig:
        state = self._read_state()
        for version in state.versions:
            if version.version_id == version_id:
                return version
        raise KeyError(f"Evaluation config version not found: {version_id}")

    def create_version(
        self,
        *,
        benchmark_scenario_ids: list[str],
        benchmark_max_turns: int,
        required_mean_score_delta: float,
        required_win_rate: float,
        require_compliance_non_regression: bool,
        diff_summary: str | None = None,
    ) -> EvaluationConfig:
        state = self._read_state()
        version = EvaluationConfig(
            version_id=f"v{len(state.versions) + 1}",
            benchmark_scenario_ids=benchmark_scenario_ids,
            benchmark_max_turns=benchmark_max_turns,
            required_mean_score_delta=required_mean_score_delta,
            required_win_rate=required_win_rate,
            require_compliance_non_regression=require_compliance_non_regression,
            diff_summary=diff_summary,
            created_at=self._utc_now(),
        )
        state.versions.append(version)
        self._write_state(state)
        return version

    def activate_version(self, version_id: str) -> str:
        state = self._read_state()
        self.get_version(version_id)
        state.active_version_id = version_id
        self._write_state(state)
        return version_id

    def list_versions(self) -> list[EvaluationConfig]:
        return list(reversed(self._read_state().versions))

    def _seed_state(self) -> EvaluationConfigState:
        initial = EvaluationConfig(
            version_id="v1",
            benchmark_scenario_ids=[
                "hard_reject_final_notice",
                "willing_but_constrained_payment_plan",
                "disputes_outstanding_amount_needs_reconciliation",
                "wants_fast_closure_but_negotiates_terms",
            ],
            benchmark_max_turns=24,
            required_mean_score_delta=0.25,
            required_win_rate=0.5,
            require_compliance_non_regression=True,
            diff_summary=None,
            created_at=self._utc_now(),
        )
        return EvaluationConfigState(active_version_id=initial.version_id, versions=[initial])

    def _read_state(self) -> EvaluationConfigState:
        return EvaluationConfigState.model_validate(json.loads(self.path.read_text()))

    def _write_state(self, state: EvaluationConfigState) -> None:
        self.path.write_text(json.dumps(state.model_dump(), indent=2))

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


evaluation_config_service = EvaluationConfigService()
