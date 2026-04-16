from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel, Field

from app.services.simulation_run_history import SimulationRunHistoryService
from evals.judgment_management_service.service import JudgmentRecordService
from evals.logging_service.logger import get_logs
from evals.tester_service import DEFAULT_SCENARIOS_PATH, ScenarioRepository


class PerformancePromptChange(BaseModel):
    agent_id: str
    old_version_id: str
    new_version_id: str
    activation_status: str
    diff_summary: str


class EvalPerformancePoint(BaseModel):
    iteration: int
    experiment_id: str
    workflow_id: str | None = None
    scenario_id: str
    overall_score: float
    verdict: str
    evaluated_at: str
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    prompt_change: PerformancePromptChange | None = None


class EvalPerformanceDataset(BaseModel):
    points: list[EvalPerformancePoint]
    available_scenarios: list[str]


class EvalPerformanceService:
    def __init__(
        self,
        run_history_service: SimulationRunHistoryService | None = None,
        judgment_record_service: JudgmentRecordService | None = None,
        scenario_repository: ScenarioRepository | None = None,
    ) -> None:
        self.run_history_service = run_history_service or SimulationRunHistoryService()
        self.judgment_record_service = judgment_record_service or JudgmentRecordService()
        self.scenario_repository = scenario_repository or ScenarioRepository(DEFAULT_SCENARIOS_PATH)

    def get_dataset(self, scenario_id: str | None = None) -> EvalPerformanceDataset:
        run_by_experiment = {run.experiment_id: run for run in self.run_history_service.list_runs()}
        scenario_index = {scenario.scenario_id: scenario for scenario in self.scenario_repository.list()}
        records = [
            record
            for record in self.judgment_record_service.list_records()
            if record.judgment is not None
        ]

        points: list[EvalPerformancePoint] = []
        for index, record in enumerate(records, start=1):
            assert record.judgment is not None
            run = run_by_experiment.get(record.experiment_id)
            inferred_scenario_id = self._resolve_scenario_id(
                experiment_id=record.experiment_id,
                run_scenario_id=run.scenario_id if run else None,
                scenario_index=scenario_index,
            )
            if scenario_id and inferred_scenario_id != scenario_id:
                continue
            workflow_id = run.workflow_id if run else self._infer_workflow_id(record.experiment_id)
            latest_evaluation = run.evaluations[-1] if run and run.evaluations else None
            prompt_versions = latest_evaluation.prompt_versions if latest_evaluation else {}

            prompt_change = None
            if record.prompt_change is not None:
                prompt_change = PerformancePromptChange(
                    agent_id=record.prompt_change.agent_id,
                    old_version_id=record.prompt_change.old_version_id,
                    new_version_id=record.prompt_change.new_version_id,
                    activation_status=record.prompt_change.activation_status,
                    diff_summary=record.prompt_change.diff_summary,
                )

            points.append(
                EvalPerformancePoint(
                    iteration=index,
                    experiment_id=record.experiment_id,
                    workflow_id=workflow_id,
                    scenario_id=inferred_scenario_id,
                    overall_score=record.judgment.overall_score,
                    verdict=record.judgment.verdict,
                    evaluated_at=record.updated_at,
                    prompt_versions=prompt_versions,
                    prompt_change=prompt_change,
                )
            )

        available_scenarios = sorted({point.scenario_id for point in points})
        return EvalPerformanceDataset(points=points, available_scenarios=available_scenarios)

    def _resolve_scenario_id(
        self,
        *,
        experiment_id: str,
        run_scenario_id: str | None,
        scenario_index: dict[str, object],
    ) -> str:
        if run_scenario_id:
            return run_scenario_id
        events = get_logs(experiment_id)
        first_borrower_message = None
        for event in events:
            if event.actor == "borrower":
                first_borrower_message = event.message_text.strip()
                break
        if not first_borrower_message:
            return "unknown"

        for scenario_id, scenario in scenario_index.items():
            opening_message = getattr(scenario, "opening_message", "")
            if isinstance(opening_message, str) and opening_message.strip() == first_borrower_message:
                return scenario_id
        return "unknown"

    def _infer_workflow_id(self, experiment_id: str) -> str | None:
        events = get_logs(experiment_id)
        for event in events:
            if event.workflow_id:
                return event.workflow_id
        return None
