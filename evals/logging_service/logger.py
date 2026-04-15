from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "chats" / "transcript_events.jsonl"
EXPERIMENT_LOGS_DIR = LOG_PATH.parent / "experiments"


@dataclass
class LogEvent:
    id: int
    experiment_id: str | None
    workflow_id: str | None
    actor: str | None
    message_text: str
    created_at: str


class LogStorageService(ABC):
    @abstractmethod
    def log(
        self,
        message: str,
        experiment_id: str | None = None,
        workflow_id: str | None = None,
        actor: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_logs(self, experiment_id: str) -> list[LogEvent]:
        raise NotImplementedError

    @abstractmethod
    def get_logs_by_workflow(self, workflow_id: str) -> list[LogEvent]:
        raise NotImplementedError


class JsonlLogStorageService(LogStorageService):
    def __init__(self, path: Path = LOG_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        EXPERIMENT_LOGS_DIR.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("")

    def log(
        self,
        message: str,
        experiment_id: str | None = None,
        workflow_id: str | None = None,
        actor: str | None = None,
    ) -> None:
        event = LogEvent(
            id=self._next_id(),
            experiment_id=experiment_id,
            workflow_id=workflow_id,
            actor=actor,
            message_text=message,
            created_at=utc_now(),
        )
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.__dict__) + "\n")
        if experiment_id:
            experiment_path = self._experiment_log_path(experiment_id)
            with experiment_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.__dict__) + "\n")

    def get_logs(self, experiment_id: str) -> list[LogEvent]:
        experiment_path = self._experiment_log_path(experiment_id)
        if experiment_path.exists():
            events = self._read_events(experiment_path)
        else:
            events = [event for event in self._read_events(self.path) if event.experiment_id == experiment_id]
        return sorted(events, key=lambda event: (event.created_at, event.id))

    def get_logs_by_workflow(self, workflow_id: str) -> list[LogEvent]:
        events = [event for event in self._read_events(self.path) if event.workflow_id == workflow_id]
        return sorted(events, key=lambda event: (event.created_at, event.id))

    def _read_events(self, path: Path) -> list[LogEvent]:
        events: list[LogEvent] = []
        if not path.exists():
            return events
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                events.append(LogEvent(**json.loads(line)))
        return events

    def _next_id(self) -> int:
        events = self._read_events(self.path)
        if not events:
            return 1
        return max(event.id for event in events) + 1

    def _experiment_log_path(self, experiment_id: str) -> Path:
        safe_name = experiment_id.replace("/", "_")
        return EXPERIMENT_LOGS_DIR / f"{safe_name}.jsonl"


class TranscriptLogger:
    def __init__(self, storage_service: LogStorageService) -> None:
        self.storage_service = storage_service

    def log(
        self,
        message: str,
        experiment_id: str | None = None,
        workflow_id: str | None = None,
        actor: str | None = None,
    ) -> None:
        self.storage_service.log(
            message=message,
            experiment_id=experiment_id,
            workflow_id=workflow_id,
            actor=actor,
        )

    def get_logs(self, experiment_id: str) -> list[LogEvent]:
        return self.storage_service.get_logs(experiment_id)

    def get_logs_by_workflow(self, workflow_id: str) -> list[LogEvent]:
        return self.storage_service.get_logs_by_workflow(workflow_id)


jsonl_log_storage_service = JsonlLogStorageService()
logger = TranscriptLogger(jsonl_log_storage_service)


def log(
    message: str,
    experiment_id: str | None = None,
    workflow_id: str | None = None,
    actor: str | None = None,
) -> None:
    logger.log(
        message=message,
        experiment_id=experiment_id,
        workflow_id=workflow_id,
        actor=actor,
    )


def get_logs(experiment_id: str) -> list[LogEvent]:
    return logger.get_logs(experiment_id)


def get_logs_by_workflow(workflow_id: str) -> list[LogEvent]:
    return logger.get_logs_by_workflow(workflow_id)
