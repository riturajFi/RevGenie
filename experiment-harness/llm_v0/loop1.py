from __future__ import annotations

from experiments.llm_v0.logs import LogCollector
from experiments.llm_v0.models import LoopSummary
from experiments.llm_v0.runtime import ExperimentRuntime
from experiments.llm_v0.store import JsonStore
from experiments.llm_v0.versioning import EvaluatorVersionManager, PromptVersionManager


class Loop1Runner:
    def __init__(
        self,
        store: JsonStore,
        runtime: ExperimentRuntime,
        prompt_manager: PromptVersionManager,
        evaluator_manager: EvaluatorVersionManager,
        logs: LogCollector,
    ) -> None:
        self.store = store
        self.runtime = runtime
        self.prompt_manager = prompt_manager
        self.evaluator_manager = evaluator_manager
        self.logs = logs

    def run(self, scenarios_path: str) -> LoopSummary:
        scenarios = self.store.load_scenarios(scenarios_path)
        if not scenarios:
            raise ValueError("No scenarios found for loop1")

        self.logs.collect(
            source="loop1",
            message="Starting Loop 1 run",
            metadata={"scenarios_path": scenarios_path, "scenario_count": len(scenarios)},
        )

        active_prompt = self.prompt_manager.get_active()
        active_evaluator = self.evaluator_manager.get_active()
        baseline_runs = [
            self.runtime.run_single_experiment("loop1_baseline", scenario, active_prompt, active_evaluator)
            for scenario in scenarios
        ]
        target_run = self.runtime.pick_target_run(baseline_runs)
        prompt_diff = self.runtime.propose_prompt_diff(
            current_prompt=active_prompt.text,
            bad_transcript=target_run.transcript.merged_transcript,
            judge_feedback=target_run.evaluation,
        )
        candidate_prompt = self.prompt_manager.create_candidate(
            text=self.runtime.apply_diff(active_prompt.text, prompt_diff.prompt_diff, active_prompt.version_id),
            diff=prompt_diff.prompt_diff,
            parent_version_id=active_prompt.version_id,
        )
        candidate_runs = [
            self.runtime.run_single_experiment("loop1_candidate", scenario, candidate_prompt, active_evaluator)
            for scenario in scenarios
        ]
        baseline_summary = self.runtime.score_summary(baseline_runs)
        candidate_summary = self.runtime.score_summary(candidate_runs)
        decision = self.runtime.compare_prompt_versions(
            active_prompt=active_prompt,
            candidate_prompt=candidate_prompt,
            baseline_runs=baseline_runs,
            candidate_runs=candidate_runs,
            baseline_summary=baseline_summary,
            candidate_summary=candidate_summary,
        )

        if decision.decision == "ADOPT":
            self.prompt_manager.adopt_candidate(candidate_prompt.version_id)
        else:
            self.prompt_manager.reject_candidate(candidate_prompt.version_id, decision.reason)

        state = self.store.load_state()
        self.logs.collect(
            source="loop1",
            message="Finished Loop 1 run",
            metadata={
                "candidate_version_id": candidate_prompt.version_id,
                "decision": decision.decision,
                "active_prompt_version": state.active_prompt_version,
            },
        )
        return LoopSummary(
            baseline_summary=baseline_summary,
            candidate_summary=candidate_summary,
            decision=decision,
            candidate_version_id=candidate_prompt.version_id,
            active_prompt_version=state.active_prompt_version,
        )
