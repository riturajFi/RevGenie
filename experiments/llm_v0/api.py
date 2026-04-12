from __future__ import annotations

from pathlib import Path

from experiments.llm_v0.logs import LogCollector
from experiments.llm_v0.loop1 import Loop1Runner
from experiments.llm_v0.loop2 import Loop2Runner
from experiments.llm_v0.models import ExperimentState, LinkedVersion, LogEntry, LoopSummary
from experiments.llm_v0.runtime import ExperimentRuntime
from experiments.llm_v0.store import JsonStore
from experiments.llm_v0.versioning import Loop1ChangeManager, Loop2ChangeManager


class ExperimentApi:
    def __init__(
        self,
        root_dir: Path | None = None,
        model: str | None = None,
        judge_model: str | None = None,
    ) -> None:
        self.store = JsonStore(root_dir)
        self.logs = LogCollector(self.store)
        self.prompt_manager = Loop1ChangeManager(self.store)
        self.evaluator_manager = Loop2ChangeManager(self.store)
        self.runtime = ExperimentRuntime(self.store, model=model, judge_model=judge_model)
        self.loop1_runner = Loop1Runner(
            store=self.store,
            runtime=self.runtime,
            prompt_manager=self.prompt_manager,
            evaluator_manager=self.evaluator_manager,
            logs=self.logs,
        )
        self.loop2_runner = Loop2Runner(
            store=self.store,
            runtime=self.runtime,
            prompt_manager=self.prompt_manager,
            evaluator_manager=self.evaluator_manager,
            logs=self.logs,
        )

    def init_experiment(self) -> ExperimentState:
        self.store.bootstrap()
        self.prompt_manager.bootstrap()
        self.evaluator_manager.bootstrap()
        return self.store.load_state()

    def get_state(self) -> ExperimentState:
        self.init_experiment()
        return self.store.load_state()

    def collect_log(
        self,
        source: str,
        message: str,
        metadata: dict | None = None,
        caller_cwd: str | None = None,
    ) -> LogEntry:
        self.init_experiment()
        return self.logs.collect(
            source=source,
            message=message,
            metadata=metadata,
            caller_cwd=caller_cwd,
        )

    def run_loop1(self, scenarios_path: str) -> LoopSummary:
        self.init_experiment()
        return self.loop1_runner.run(scenarios_path)

    def run_loop2(self, audits_path: str) -> LoopSummary:
        self.init_experiment()
        return self.loop2_runner.run(audits_path)

    def revert_loop1(self, version_id: str | None = None) -> LinkedVersion:
        self.init_experiment()
        version = self.prompt_manager.revert_to(version_id)
        self.logs.collect(
            source="api.revert_loop1",
            message="Reverted Loop 1 prompt chain",
            metadata={"active_prompt_version": version.version_id},
        )
        return version

    def revert_loop2(self, version_id: str | None = None) -> LinkedVersion:
        self.init_experiment()
        version = self.evaluator_manager.revert_to(version_id)
        self.logs.collect(
            source="api.revert_loop2",
            message="Reverted Loop 2 evaluator chain",
            metadata={"active_evaluator_version": version.version_id},
        )
        return version


def collect_log(
    source: str,
    message: str,
    metadata: dict | None = None,
    caller_cwd: str | None = None,
) -> LogEntry:
    return ExperimentApi().collect_log(
        source=source,
        message=message,
        metadata=metadata,
        caller_cwd=caller_cwd,
    )
