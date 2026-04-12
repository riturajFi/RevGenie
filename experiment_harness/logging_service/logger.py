from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class InMemoryLogStorageService(LogStorageService):
    def __init__(self) -> None:
        self._events: list[LogEvent] = []
        self._next_id = 1

    def log(
        self,
        message: str,
        experiment_id: str | None = None,
        workflow_id: str | None = None,
        actor: str | None = None,
    ) -> None:
        self._events.append(
            LogEvent(
                id=self._next_id,
                experiment_id=experiment_id,
                workflow_id=workflow_id,
                actor=actor,
                message_text=message,
                created_at=utc_now(),
            )
        )
        self._next_id += 1

    def get_logs(self, experiment_id: str) -> list[LogEvent]:
        events = [event for event in self._events if event.experiment_id == experiment_id]
        return sorted(events, key=lambda event: (event.created_at, event.id))

    def get_logs_by_workflow(self, workflow_id: str) -> list[LogEvent]:
        events = [event for event in self._events if event.workflow_id == workflow_id]
        return sorted(events, key=lambda event: (event.created_at, event.id))


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


in_memory_log_storage_service = InMemoryLogStorageService()
logger = TranscriptLogger(in_memory_log_storage_service)


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
