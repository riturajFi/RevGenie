from __future__ import annotations

from experiments.llm_v0.logs import LogCollector
from experiments.llm_v0.models import LoopSummary
from experiments.llm_v0.runtime import ExperimentRuntime
from experiments.llm_v0.store import JsonStore
from experiments.llm_v0.versioning import EvaluatorVersionManager, PromptVersionManager


class Loop2Runner:
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

    def run(self, audits_path: str) -> LoopSummary:
        audits = self.store.load_scenarios(audits_path)
        if not audits:
            raise ValueError("No audits found for loop2")

        self.logs.collect(
            source="loop2",
            message="Starting Loop 2 run",
            metadata={"audits_path": audits_path, "audit_count": len(audits)},
        )

        active_prompt = self.prompt_manager.get_active()
        active_evaluator = self.evaluator_manager.get_active()
        baseline_runs = [
            self.runtime.run_single_experiment("loop2_baseline", audit, active_prompt, active_evaluator)
            for audit in audits
        ]
        evaluator_diff = self.runtime.propose_evaluator_diff(active_evaluator.text, baseline_runs)
        candidate_evaluator = self.evaluator_manager.create_candidate(
            text=self.runtime.apply_diff(
                active_evaluator.text,
                evaluator_diff.evaluator_diff,
                active_evaluator.version_id,
            ),
            diff=evaluator_diff.evaluator_diff,
            parent_version_id=active_evaluator.version_id,
        )
        candidate_runs = [
            self.runtime.run_single_experiment("loop2_candidate", audit, active_prompt, candidate_evaluator)
            for audit in audits
        ]
        baseline_summary = self.runtime.score_summary(baseline_runs)
        candidate_summary = self.runtime.score_summary(candidate_runs)
        decision = self.runtime.compare_evaluator_versions(
            active_evaluator=active_evaluator,
            candidate_evaluator=candidate_evaluator,
            baseline_runs=baseline_runs,
            candidate_runs=candidate_runs,
            baseline_summary=baseline_summary,
            candidate_summary=candidate_summary,
            identified_flaws=evaluator_diff.identified_flaws,
        )

        if decision.decision == "ADOPT":
            self.evaluator_manager.adopt_candidate(candidate_evaluator.version_id)
        else:
            self.evaluator_manager.reject_candidate(candidate_evaluator.version_id, decision.reason)

        state = self.store.load_state()
        self.logs.collect(
            source="loop2",
            message="Finished Loop 2 run",
            metadata={
                "candidate_version_id": candidate_evaluator.version_id,
                "decision": decision.decision,
                "active_evaluator_version": state.active_evaluator_version,
            },
        )
        return LoopSummary(
            baseline_summary=baseline_summary,
            candidate_summary=candidate_summary,
            decision=decision,
            candidate_version_id=candidate_evaluator.version_id,
            active_evaluator_version=state.active_evaluator_version,
        )
