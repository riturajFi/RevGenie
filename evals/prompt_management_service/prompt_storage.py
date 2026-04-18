from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from app.agents.prompts.assessment import ASSESSMENT_SYSTEM_PROMPT
from app.agents.prompts.final_notice import FINAL_NOTICE_SYSTEM_PROMPT
from app.agents.prompts.resolution import RESOLUTION_SYSTEM_PROMPT


VALID_AGENT_IDS = {"agent_1", "agent_2", "agent_3"}
STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "evals" / "prompt_management.json"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_prompt_lines(prompt_value: str | list[str]) -> list[str]:
    if isinstance(prompt_value, list):
        return [str(line) for line in prompt_value]
    return prompt_value.splitlines()


@dataclass
class PromptStorageVersion:
    id: int
    agent_id: str
    version_id: str
    parent_version_id: str | None
    prompt_lines: list[str]
    diff_summary: str | None
    created_at: datetime

    @property
    def prompt_text(self) -> str:
        return "\n".join(self.prompt_lines)


class PromptStorageService(ABC):
    @abstractmethod
    def get_active_prompt(self, agent_id: str) -> PromptStorageVersion:
        raise NotImplementedError

    @abstractmethod
    def get_prompt_version(self, agent_id: str, version_id: str) -> PromptStorageVersion:
        raise NotImplementedError

    @abstractmethod
    def get_prompt_history(self, agent_id: str) -> list[PromptStorageVersion]:
        raise NotImplementedError

    @abstractmethod
    def create_prompt_version(
        self,
        agent_id: str,
        prompt_text: str | list[str],
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


class JsonPromptStorageService(PromptStorageService):
    def __init__(self, path: Path = STORE_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_state(self._seed_state())

    def get_active_prompt(self, agent_id: str) -> PromptStorageVersion:
        self._ensure_agent(agent_id)
        state = self._read_state()
        active_version_id = state["active_versions"].get(agent_id)
        if active_version_id is None:
            raise KeyError("Active prompt not found")
        return self._get_version_from_state(state, agent_id, active_version_id)

    def get_prompt_version(self, agent_id: str, version_id: str) -> PromptStorageVersion:
        self._ensure_agent(agent_id)
        state = self._read_state()
        return self._get_version_from_state(state, agent_id, version_id)

    def get_prompt_history(self, agent_id: str) -> list[PromptStorageVersion]:
        self._ensure_agent(agent_id)
        state = self._read_state()
        versions = [self._deserialize_version(item) for item in state["versions_by_agent"].get(agent_id, [])]
        return list(reversed(versions))

    def create_prompt_version(
        self,
        agent_id: str,
        prompt_text: str | list[str],
        parent_version_id: str | None = None,
        diff_summary: str | None = None,
    ) -> PromptStorageVersion:
        self._ensure_agent(agent_id)
        state = self._read_state()
        if parent_version_id is not None:
            self._get_version_from_state(state, agent_id, parent_version_id)
        versions = state["versions_by_agent"][agent_id]
        version = PromptStorageVersion(
            id=state["next_id"],
            agent_id=agent_id,
            version_id=f"v{len(versions) + 1}",
            parent_version_id=parent_version_id,
            prompt_lines=normalize_prompt_lines(prompt_text),
            diff_summary=diff_summary,
            created_at=utc_now(),
        )
        state["next_id"] += 1
        versions.append(self._serialize_version(version))
        self._write_state(state)
        return version

    def activate_version(self, agent_id: str, version_id: str) -> str:
        self._ensure_agent(agent_id)
        state = self._read_state()
        version = self._get_version_from_state(state, agent_id, version_id)
        state["active_versions"][agent_id] = version.version_id
        self._write_state(state)
        return version.version_id

    def rollback(self, agent_id: str, version_id: str) -> str:
        return self.activate_version(agent_id, version_id)

    def _seed_state(self) -> dict:
        seeded_versions = {
            "agent_1": [
                self._serialize_version(
                    PromptStorageVersion(
                        id=1,
                        agent_id="agent_1",
                        version_id="v1",
                        parent_version_id=None,
                        prompt_lines=normalize_prompt_lines(ASSESSMENT_SYSTEM_PROMPT),
                        diff_summary=None,
                        created_at=utc_now(),
                    )
                )
            ],
            "agent_2": [
                self._serialize_version(
                    PromptStorageVersion(
                        id=2,
                        agent_id="agent_2",
                        version_id="v1",
                        parent_version_id=None,
                        prompt_lines=normalize_prompt_lines(RESOLUTION_SYSTEM_PROMPT),
                        diff_summary=None,
                        created_at=utc_now(),
                    )
                )
            ],
            "agent_3": [
                self._serialize_version(
                    PromptStorageVersion(
                        id=3,
                        agent_id="agent_3",
                        version_id="v1",
                        parent_version_id=None,
                        prompt_lines=normalize_prompt_lines(FINAL_NOTICE_SYSTEM_PROMPT),
                        diff_summary=None,
                        created_at=utc_now(),
                    )
                )
            ],
        }
        return {
            "next_id": 4,
            "active_versions": {
                "agent_1": "v1",
                "agent_2": "v1",
                "agent_3": "v1",
            },
            "versions_by_agent": seeded_versions,
        }

    def _ensure_agent(self, agent_id: str) -> None:
        if agent_id not in VALID_AGENT_IDS:
            raise KeyError("Agent prompt not found")

    def _read_state(self) -> dict:
        return json.loads(self.path.read_text())

    def _write_state(self, state: dict) -> None:
        self.path.write_text(json.dumps(state, indent=2))

    def _get_version_from_state(self, state: dict, agent_id: str, version_id: str) -> PromptStorageVersion:
        for item in state["versions_by_agent"].get(agent_id, []):
            version = self._deserialize_version(item)
            if version.version_id == version_id:
                return version
        raise KeyError("Version not found")

    def _serialize_version(self, version: PromptStorageVersion) -> dict:
        return {
            "id": version.id,
            "agent_id": version.agent_id,
            "version_id": version.version_id,
            "parent_version_id": version.parent_version_id,
            "prompt_text": version.prompt_lines,
            "diff_summary": version.diff_summary,
            "created_at": version.created_at.isoformat(),
        }

    def _deserialize_version(self, payload: dict) -> PromptStorageVersion:
        prompt_payload = payload.get("prompt_text", payload.get("prompt_lines", ""))
        return PromptStorageVersion(
            id=payload["id"],
            agent_id=payload["agent_id"],
            version_id=payload["version_id"],
            parent_version_id=payload.get("parent_version_id"),
            prompt_lines=normalize_prompt_lines(prompt_payload),
            diff_summary=payload.get("diff_summary"),
            created_at=datetime.fromisoformat(payload["created_at"]),
        )


json_prompt_storage_service = JsonPromptStorageService()
