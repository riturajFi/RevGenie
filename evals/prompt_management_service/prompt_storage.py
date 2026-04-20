from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


VALID_AGENT_IDS = {"agent_1", "agent_2", "agent_3"}
STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "evals" / "prompt_management.json"
LEGACY_STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "evals" / "prompt_management.py"
SEED_PROMPT_TEXT = {
    "agent_1": [
        "You are Agent 1, the Assessment agent for a debt collections workflow.",
        "Use the active prompt store as the source of truth.",
    ],
    "agent_2": [
        "You are Agent 2, the Resolution agent for a debt collections workflow.",
        "Use the active prompt store as the source of truth.",
    ],
    "agent_3": [
        "You are Agent 3, the Final Notice agent for a debt collections workflow.",
        "Use the active prompt store as the source of truth.",
    ],
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_prompt_lines(prompt_value: str | list[str]) -> list[str]:
    if isinstance(prompt_value, list):
        return [str(line) for line in prompt_value]
    return str(prompt_value).splitlines()


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
    def __init__(self, path: Path = STORE_PATH, legacy_path: Path = LEGACY_STORE_PATH) -> None:
        self.path = path
        self.legacy_path = legacy_path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_store_exists()
        self._migrate_legacy_python_store_if_newer()

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

    def _ensure_store_exists(self) -> None:
        if self.path.exists():
            return
        self._write_state(self._seed_state())

    def _migrate_legacy_python_store_if_newer(self) -> None:
        if not self.legacy_path.exists():
            return

        legacy_state = self._read_python_state(self.legacy_path)
        current_state = self._read_state()
        legacy_next_id = int(legacy_state.get("next_id", 0))
        current_next_id = int(current_state.get("next_id", 0))

        if legacy_next_id > current_next_id:
            self._write_state(legacy_state)

    def _seed_state(self) -> dict:
        seeded_versions = {
            "agent_1": [
                self._serialize_version(
                    PromptStorageVersion(
                        id=1,
                        agent_id="agent_1",
                        version_id="v1",
                        parent_version_id=None,
                        prompt_lines=SEED_PROMPT_TEXT["agent_1"],
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
                        prompt_lines=SEED_PROMPT_TEXT["agent_2"],
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
                        prompt_lines=SEED_PROMPT_TEXT["agent_3"],
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
        payload = json.loads(self.path.read_text())
        if not isinstance(payload, dict):
            raise ValueError("Prompt storage file is invalid")
        return payload

    def _read_python_state(self, path: Path) -> dict:
        namespace: dict[str, object] = {}
        exec(path.read_text(), {"__builtins__": {}}, namespace)
        state = namespace.get("STATE")
        if not isinstance(state, dict):
            raise ValueError("Legacy prompt storage file is invalid")
        return state

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
            "prompt_text": version.prompt_text,
            "diff_summary": version.diff_summary,
            "created_at": version.created_at.isoformat(),
        }

    def _deserialize_version(self, payload: dict) -> PromptStorageVersion:
        prompt_payload = payload.get("prompt_text", payload.get("prompt_lines", ""))
        created_at_value = payload.get("created_at")
        if isinstance(created_at_value, datetime):
            created_at = created_at_value
        elif isinstance(created_at_value, str):
            created_at = datetime.fromisoformat(created_at_value)
        else:
            created_at = utc_now()
        return PromptStorageVersion(
            id=payload["id"],
            agent_id=payload["agent_id"],
            version_id=payload["version_id"],
            parent_version_id=payload.get("parent_version_id"),
            prompt_lines=normalize_prompt_lines(prompt_payload),
            diff_summary=payload.get("diff_summary"),
            created_at=created_at,
        )


json_prompt_storage_service = JsonPromptStorageService()
python_file_prompt_storage_service = json_prompt_storage_service
PythonFilePromptStorageService = JsonPromptStorageService
