from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from experiments.llm_v0.models import (
    ExperimentRunRecord,
    ExperimentState,
    LinkedVersion,
    LogEntry,
    Scenario,
    TokenCountRecord,
    VersionAuditEvent,
)

THIS_DIR = Path(__file__).resolve().parent


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_merged_transcript(agent_1_chat: str, agent_2_voice: str, agent_3_chat: str) -> str:
    return (
        "=== Agent 1 Chat Transcript ===\n"
        f"{agent_1_chat.strip()}\n\n"
        "=== Agent 2 Voice Transcript ===\n"
        f"{agent_2_voice.strip()}\n\n"
        "=== Agent 3 Chat Transcript ===\n"
        f"{agent_3_chat.strip()}"
    )


class JsonStore:
    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or THIS_DIR
        self.data_dir = self.root_dir / "data"
        self.prompts_dir = self.data_dir / "prompts"
        self.evaluators_dir = self.data_dir / "evaluators"
        self.runs_dir = self.data_dir / "runs"
        self.audit_runs_dir = self.data_dir / "audit_runs"
        self.logs_dir = self.data_dir / "logs"
        self.history_dir = self.data_dir / "history"
        self.token_counts_dir = self.data_dir / "token_counts"
        self.state_path = self.data_dir / "state.json"

    def bootstrap(self) -> None:
        for path in [
            self.prompts_dir,
            self.evaluators_dir,
            self.runs_dir,
            self.audit_runs_dir,
            self.logs_dir,
            self.history_dir,
            self.token_counts_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

        if not self.state_path.exists():
            self.save_state(ExperimentState())

    def load_state(self) -> ExperimentState:
        self.bootstrap()
        return ExperimentState.model_validate(self._read_json(self.state_path))

    def save_state(self, state: ExperimentState) -> None:
        self._write_json(self.state_path, state.model_dump())

    def reserve_next_version_id(self, kind: str) -> str:
        state = self.load_state()
        if kind == "prompt":
            version_id = f"prompt_v{state.next_prompt_number}"
            state.next_prompt_number += 1
        else:
            version_id = f"evaluator_v{state.next_evaluator_number}"
            state.next_evaluator_number += 1
        self.save_state(state)
        return version_id

    def reserve_next_log_sequence(self) -> int:
        state = self.load_state()
        sequence = state.next_log_sequence
        state.next_log_sequence += 1
        self.save_state(state)
        return sequence

    def load_version(self, kind: str, version_id: str) -> LinkedVersion:
        return LinkedVersion.model_validate(self._read_json(self._version_path(kind, version_id)))

    def load_all_versions(self, kind: str) -> list[LinkedVersion]:
        return [
            LinkedVersion.model_validate(self._read_json(path))
            for path in self._version_dir(kind).glob(f"{kind}_v*.json")
        ]

    def save_version(self, version: LinkedVersion) -> None:
        self._write_json(self._version_path(version.kind, version.version_id), version.model_dump())

    def delete_version(self, kind: str, version_id: str) -> None:
        path = self._version_path(kind, version_id)
        if path.exists():
            path.unlink()

    def append_log(self, entry: LogEntry) -> None:
        self._append_jsonl(self.logs_dir / "events.jsonl", entry.model_dump())

    def append_history(self, event: VersionAuditEvent) -> None:
        self._append_jsonl(self.history_dir / f"{event.version_kind}_history.jsonl", event.model_dump())

    def append_token_count(self, record: TokenCountRecord) -> None:
        self._append_jsonl(self.token_counts_dir / "token_counts.jsonl", record.model_dump())

    def save_run(self, record: ExperimentRunRecord) -> None:
        target_dir = self.audit_runs_dir if record.loop_name.startswith("loop2") else self.runs_dir
        self._write_json(target_dir / f"{record.run_id}.json", record.model_dump())

    def load_scenarios(self, path: str) -> list[Scenario]:
        payload = self._read_json(Path(path))
        return [Scenario.model_validate(item) for item in payload]

    def _version_dir(self, kind: str) -> Path:
        return self.prompts_dir if kind == "prompt" else self.evaluators_dir

    def _version_path(self, kind: str, version_id: str) -> Path:
        return self._version_dir(kind) / f"{version_id}.json"

    def _read_json(self, path: Path) -> dict[str, Any] | list[Any]:
        return json.loads(path.read_text())

    def _write_json(self, path: Path, payload: dict[str, Any] | list[Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2))

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")
