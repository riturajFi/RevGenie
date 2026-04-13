from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel


THIS_DIR = Path(__file__).resolve().parent
DEFAULT_PROPOSER_PROMPT_PATH = THIS_DIR.parent / "data" / "proposer_prompt_versions.json"
DEFAULT_PROPOSER_PROMPT_TEXT = (
    "You improve one collections agent prompt. "
    "Preserve intent, improve failures, and do not make it longer than needed."
)


class ProposerPromptVersion(BaseModel):
    version_id: str
    prompt_text: str
    diff_summary: str | None = None
    created_at: str


class ProposerPromptManagerState(BaseModel):
    active_version_id: str
    versions: list[ProposerPromptVersion]


class ProposerPromptManager:
    def __init__(self, path: Path = DEFAULT_PROPOSER_PROMPT_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write_state(
                ProposerPromptManagerState(
                    active_version_id="v1",
                    versions=[
                        ProposerPromptVersion(
                            version_id="v1",
                            prompt_text=DEFAULT_PROPOSER_PROMPT_TEXT,
                            diff_summary=None,
                            created_at=self._utc_now(),
                        )
                    ],
                )
            )

    def get_active_prompt(self) -> ProposerPromptVersion:
        state = self._read_state()
        return self._get_version(state, state.active_version_id)

    def create_prompt_version(
        self,
        prompt_text: str,
        diff_summary: str | None = None,
    ) -> ProposerPromptVersion:
        state = self._read_state()
        version = ProposerPromptVersion(
            version_id=f"v{len(state.versions) + 1}",
            prompt_text=prompt_text,
            diff_summary=diff_summary,
            created_at=self._utc_now(),
        )
        state.versions.append(version)
        self._write_state(state)
        return version

    def activate_version(self, version_id: str) -> str:
        state = self._read_state()
        version = self._get_version(state, version_id)
        state.active_version_id = version.version_id
        self._write_state(state)
        return version.version_id

    def rollback_version(self, version_id: str) -> str:
        return self.activate_version(version_id)

    def get_history(self) -> list[ProposerPromptVersion]:
        state = self._read_state()
        return list(reversed(state.versions))

    def _read_state(self) -> ProposerPromptManagerState:
        return ProposerPromptManagerState.model_validate(json.loads(self.path.read_text()))

    def _write_state(self, state: ProposerPromptManagerState) -> None:
        self.path.write_text(json.dumps(state.model_dump(), indent=2))

    def _get_version(
        self,
        state: ProposerPromptManagerState,
        version_id: str,
    ) -> ProposerPromptVersion:
        for version in state.versions:
            if version.version_id == version_id:
                return version
        raise KeyError(f"Proposer prompt version not found: {version_id}")

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
