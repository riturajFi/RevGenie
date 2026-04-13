from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field


THIS_DIR = Path(__file__).resolve().parent
DEFAULT_METRICS_PATH = THIS_DIR.parent / "data" / "judge_metrics.json"


class MetricDefinition(BaseModel):
    metric_id: str
    name: str
    description: str
    score_type: str
    policy_references: list[str] = Field(default_factory=list)


class MetricVersion(BaseModel):
    version_id: str
    metrics_key: str
    metrics: list[MetricDefinition]
    diff_summary: str | None = None
    created_at: str


class MetricsRegistryState(BaseModel):
    active_versions: dict[str, str] = Field(default_factory=dict)
    versions_by_key: dict[str, list[MetricVersion]] = Field(default_factory=dict)


class MetricsRegistry:
    def __init__(self, path: Path = DEFAULT_METRICS_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def get_active_metrics(self, metrics_key: str) -> MetricVersion:
        state = self._read_state()
        active_version_id = state.active_versions.get(metrics_key)
        if active_version_id is None:
            raise KeyError(f"Active metrics not found for key: {metrics_key}")
        return self._get_version(state, metrics_key, active_version_id)

    def create_metrics_version(
        self,
        metrics_key: str,
        metrics: list[MetricDefinition],
        diff_summary: str | None = None,
    ) -> MetricVersion:
        state = self._read_state()
        versions = state.versions_by_key.setdefault(metrics_key, [])
        version = MetricVersion(
            version_id=f"v{len(versions) + 1}",
            metrics_key=metrics_key,
            metrics=metrics,
            diff_summary=diff_summary,
            created_at=self._utc_now(),
        )
        versions.append(version)
        self._write_state(state)
        return version

    def activate_version(self, metrics_key: str, version_id: str) -> str:
        state = self._read_state()
        version = self._get_version(state, metrics_key, version_id)
        state.active_versions[metrics_key] = version.version_id
        self._write_state(state)
        return version.version_id

    def get_metrics_version(self, metrics_key: str, version_id: str) -> MetricVersion:
        state = self._read_state()
        return self._get_version(state, metrics_key, version_id)

    def rollback_version(self, metrics_key: str, version_id: str) -> str:
        return self.activate_version(metrics_key, version_id)

    def get_history(self, metrics_key: str) -> list[MetricVersion]:
        state = self._read_state()
        return list(reversed(state.versions_by_key.get(metrics_key, [])))

    def _read_state(self) -> MetricsRegistryState:
        payload = json.loads(self.path.read_text())
        if "active_versions" not in payload:
            metrics_key = payload["key"]
            state = MetricsRegistryState(
                active_versions={metrics_key: "v1"},
                versions_by_key={
                    metrics_key: [
                        MetricVersion(
                            version_id="v1",
                            metrics_key=metrics_key,
                            metrics=[MetricDefinition.model_validate(item) for item in payload["metrics"]],
                            diff_summary=None,
                            created_at=self._utc_now(),
                        )
                    ]
                },
            )
            self._write_state(state)
            return state
        return MetricsRegistryState.model_validate(payload)

    def _write_state(self, state: MetricsRegistryState) -> None:
        self.path.write_text(json.dumps(state.model_dump(), indent=2))

    def _get_version(
        self,
        state: MetricsRegistryState,
        metrics_key: str,
        version_id: str,
    ) -> MetricVersion:
        for version in state.versions_by_key.get(metrics_key, []):
            if version.version_id == version_id:
                return version
        raise KeyError(f"Metrics version not found for key={metrics_key} version={version_id}")

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
