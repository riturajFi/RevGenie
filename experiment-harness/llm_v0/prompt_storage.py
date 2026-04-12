from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone


VALID_AGENT_IDS = {"agent_1", "agent_2", "agent_3"}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PromptStorageVersion:
    id: int
    agent_id: str
    version_id: str
    parent_version_id: str | None
    prompt_text: str
    diff_summary: str | None
    created_at: datetime


class PromptStorageService(ABC):
    @abstractmethod
    def get_active_prompt(self, agent_id: str) -> PromptStorageVersion:
        raise NotImplementedError

    @abstractmethod
    def get_prompt_history(self, agent_id: str) -> list[PromptStorageVersion]:
        raise NotImplementedError

    @abstractmethod
    def create_prompt_version(
        self,
        agent_id: str,
        prompt_text: str,
        parent_version_id: str | None = None,
        diff_summary: str | None = None,
    ) -> PromptStorageVersion:
        raise NotImplementedError

    @abstractmethod
    def activate_version(self, agent_id: str, version_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def rollback(self, agent_id: str, version_id: str) -> str:
        raise NotImplementedError


class InMemoryPromptStorageService(PromptStorageService):
    def __init__(self) -> None:
        self._versions_by_agent: dict[str, list[PromptStorageVersion]] = {}
        self._active_versions: dict[str, str] = {}
        self._next_id = 1
        self._seed_defaults()

    def get_active_prompt(self, agent_id: str) -> PromptStorageVersion:
        self._ensure_agent(agent_id)
        active_version_id = self._active_versions.get(agent_id)
        if active_version_id is None:
            raise KeyError("Active prompt not found")
        return self._get_version(agent_id, active_version_id)

    def get_prompt_history(self, agent_id: str) -> list[PromptStorageVersion]:
        self._ensure_agent(agent_id)
        return list(reversed(self._versions_by_agent.get(agent_id, [])))

    def create_prompt_version(
        self,
        agent_id: str,
        prompt_text: str,
        parent_version_id: str | None = None,
        diff_summary: str | None = None,
    ) -> PromptStorageVersion:
        self._ensure_agent(agent_id)
        if parent_version_id is not None:
            self._get_version(agent_id, parent_version_id)
        version = PromptStorageVersion(
            id=self._next_id,
            agent_id=agent_id,
            version_id=f"v{len(self._versions_by_agent[agent_id]) + 1}",
            parent_version_id=parent_version_id,
            prompt_text=prompt_text,
            diff_summary=diff_summary,
            created_at=utc_now(),
        )
        self._next_id += 1
        self._versions_by_agent[agent_id].append(version)
        return version

    def activate_version(self, agent_id: str, version_id: str) -> str:
        self._ensure_agent(agent_id)
        version = self._get_version(agent_id, version_id)
        self._active_versions[agent_id] = version.version_id
        return version.version_id

    def rollback(self, agent_id: str, version_id: str) -> str:
        return self.activate_version(agent_id, version_id)

    def _seed_defaults(self) -> None:
        for agent_id in sorted(VALID_AGENT_IDS):
            self._versions_by_agent[agent_id] = []
            version = PromptStorageVersion(
                id=self._next_id,
                agent_id=agent_id,
                version_id="v1",
                parent_version_id=None,
                prompt_text=f"{agent_id} default prompt",
                diff_summary=None,
                created_at=utc_now(),
            )
            self._next_id += 1
            self._versions_by_agent[agent_id].append(version)
            self._active_versions[agent_id] = version.version_id

    def _ensure_agent(self, agent_id: str) -> None:
        if agent_id not in VALID_AGENT_IDS:
            raise KeyError("Agent prompt not found")

    def _get_version(self, agent_id: str, version_id: str) -> PromptStorageVersion:
        for version in self._versions_by_agent.get(agent_id, []):
            if version.version_id == version_id:
                return version
        raise KeyError("Version not found")


in_memory_prompt_storage_service = InMemoryPromptStorageService()
