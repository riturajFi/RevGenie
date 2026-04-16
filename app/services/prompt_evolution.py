from __future__ import annotations

from difflib import ndiff
from typing import Literal

from pydantic import BaseModel, Field

from evals.prompt_management_service.prompt_storage import (
    PromptStorageVersion,
    PromptStorageService,
    json_prompt_storage_service,
)


class PromptDiffLine(BaseModel):
    line_type: Literal["add", "remove", "context"]
    text: str


class PromptVersionEvolution(BaseModel):
    version_id: str
    parent_version_id: str | None = None
    created_at: str
    diff_summary: str | None = None
    prompt_line_count: int
    previous_version_id: str | None = None
    diff_lines: list[PromptDiffLine] = Field(default_factory=list)


class PromptEvolutionResponse(BaseModel):
    agent_id: str
    active_version_id: str
    versions: list[PromptVersionEvolution]


class PromptEvolutionService:
    def __init__(self, prompt_service: PromptStorageService | None = None) -> None:
        self.prompt_service = prompt_service or json_prompt_storage_service

    def get_evolution(self, agent_id: str) -> PromptEvolutionResponse:
        active = self.prompt_service.get_active_prompt(agent_id)
        history = self.prompt_service.get_prompt_history(agent_id)
        ordered_versions = sorted(history, key=self._version_sort_key)

        versions: list[PromptVersionEvolution] = []
        previous: PromptStorageVersion | None = None
        for version in ordered_versions:
            versions.append(
                PromptVersionEvolution(
                    version_id=version.version_id,
                    parent_version_id=version.parent_version_id,
                    created_at=version.created_at.isoformat(),
                    diff_summary=version.diff_summary,
                    prompt_line_count=len(version.prompt_lines),
                    previous_version_id=previous.version_id if previous else None,
                    diff_lines=self._build_diff(previous.prompt_lines, version.prompt_lines) if previous else [],
                )
            )
            previous = version

        return PromptEvolutionResponse(
            agent_id=agent_id,
            active_version_id=active.version_id,
            versions=versions,
        )

    def _build_diff(self, previous_lines: list[str], current_lines: list[str]) -> list[PromptDiffLine]:
        diff_lines: list[PromptDiffLine] = []
        for line in ndiff(previous_lines, current_lines):
            prefix = line[:2]
            content = line[2:]
            if prefix == "? ":
                continue
            if prefix == "+ ":
                diff_lines.append(PromptDiffLine(line_type="add", text=content))
                continue
            if prefix == "- ":
                diff_lines.append(PromptDiffLine(line_type="remove", text=content))
                continue
            diff_lines.append(PromptDiffLine(line_type="context", text=content))
        return diff_lines

    def _version_sort_key(self, version: PromptStorageVersion) -> tuple[int, str]:
        raw = version.version_id
        if raw.startswith("v") and raw[1:].isdigit():
            return (int(raw[1:]), raw)
        return (0, raw)
