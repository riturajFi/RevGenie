from __future__ import annotations

import json
import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from evals.logging_service.logger import LogEvent, get_logs
from evals.prompt_management_service.prompt_storage import (
    PromptStorageService,
    json_prompt_storage_service,
)
from evals.judgment_management_service.service import JudgmentRecordService
from evals.judge_service.service import JudgeService
from evals.proposer_prompt_management_service.service import ProposerPromptManager


class PromptChangeApplyRequest(BaseModel):
    experiment_id: str
    target_agent_id: str
    force_activate: bool = True


class PromptChangeDraft(BaseModel):
    append_prompt_lines: list[str]
    diff_summary: str
    why_this_change: str


class PromptChangeApplyResult(BaseModel):
    agent_id: str
    old_version_id: str
    new_version_id: str
    diff_summary: str
    activation_status: str


class PromptChangeProposer:
    def __init__(
        self,
        prompt_service: PromptStorageService | None = None,
        judge_service: JudgeService | None = None,
        proposer_prompt_manager: ProposerPromptManager | None = None,
        judgment_record_service: JudgmentRecordService | None = None,
        model: str | None = None,
    ) -> None:
        self.prompt_service = prompt_service or json_prompt_storage_service
        self.judge_service = judge_service or JudgeService()
        self.proposer_prompt_manager = proposer_prompt_manager or ProposerPromptManager()
        self.judgment_record_service = judgment_record_service or JudgmentRecordService()
        self.model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def apply_change(
        self,
        experiment_id: str,
        target_agent_id: str,
        force_activate: bool = True,
    ) -> PromptChangeApplyResult:
        active_prompt = self.prompt_service.get_active_prompt(target_agent_id)
        judge_result = self.judge_service.get_judgment(experiment_id)
        transcript = self._load_transcript(experiment_id, target_agent_id)
        draft = self._propose_prompt_change(
            target_agent_id=target_agent_id,
            current_prompt=active_prompt.prompt_text,
            current_prompt_lines=active_prompt.prompt_lines,
            judge_result=judge_result,
            transcript=transcript,
        )
        new_prompt_lines = self._append_prompt_lines(active_prompt.prompt_lines, draft.append_prompt_lines)
        new_version = self.prompt_service.create_prompt_version(
            agent_id=target_agent_id,
            prompt_text=new_prompt_lines,
            parent_version_id=active_prompt.version_id,
            diff_summary=draft.diff_summary,
        )
        activation_status = "inactive"
        if force_activate:
            self.prompt_service.activate_version(target_agent_id, new_version.version_id)
            activation_status = "active"
        result = PromptChangeApplyResult(
            agent_id=target_agent_id,
            old_version_id=active_prompt.version_id,
            new_version_id=new_version.version_id,
            diff_summary=draft.diff_summary,
            activation_status=activation_status,
        )
        self.judgment_record_service.save_prompt_change(experiment_id, result)
        return result

    def _propose_prompt_change(
        self,
        target_agent_id: str,
        current_prompt: str,
        current_prompt_lines: list[str],
        judge_result,
        transcript: str,
    ) -> PromptChangeDraft:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{human_prompt}"),
            ]
        )
        llm = ChatOpenAI(model=self.model_name, temperature=0)
        chain = prompt | llm.with_structured_output(PromptChangeDraft)
        proposer_prompt = self.proposer_prompt_manager.get_active_prompt()
        return chain.invoke(
            {
                "system_prompt": proposer_prompt.prompt_text,
                "human_prompt": self._build_human_prompt(
                    target_agent_id=target_agent_id,
                    current_prompt=current_prompt,
                    current_prompt_lines=current_prompt_lines,
                    judge_result=judge_result.model_dump(),
                    transcript=transcript,
                ),
            }
        )

    def _build_human_prompt(
        self,
        target_agent_id: str,
        current_prompt: str,
        current_prompt_lines: list[str],
        judge_result: dict,
        transcript: str,
    ) -> str:
        return (
            f"Target agent: {target_agent_id}\n\n"
            f"Current prompt as readable text:\n{current_prompt}\n\n"
            f"Current prompt lines JSON:\n{json.dumps(current_prompt_lines, indent=2)}\n\n"
            f"Judge output:\n{json.dumps(judge_result, indent=2)}\n\n"
            f"Relevant transcript for this target agent only:\n{transcript}\n\n"
            "Return JSON with:\n"
            "- append_prompt_lines\n"
            "- diff_summary\n"
            "- why_this_change\n"
            "Rules for append_prompt_lines:\n"
            "- Return only new lines that can be appended to the existing prompt.\n"
            "- Use one string per prompt line.\n"
            "- Use empty strings for blank lines.\n"
            "- Prefer adding new sections, examples, or clarifying instructions.\n"
            "- Do not rewrite or repeat existing lines.\n"
            "- Keep additions concise and readable.\n"
        )

    def _append_prompt_lines(self, current_prompt_lines: list[str], append_prompt_lines: list[str]) -> list[str]:
        if not append_prompt_lines:
            return list(current_prompt_lines)

        merged = list(current_prompt_lines)
        if merged and merged[-1] != "":
            merged.append("")
        merged.extend(append_prompt_lines)
        return merged

    def _load_transcript(self, experiment_id: str, target_agent_id: str) -> str:
        events = get_logs(experiment_id)
        events = self._filter_events_for_target_agent(events, target_agent_id)
        return "\n".join(
            f"[{event.created_at}] {event.actor or 'unknown'}: {event.message_text}"
            for event in events
        )

    def _filter_events_for_target_agent(
        self,
        events: list[LogEvent],
        target_agent_id: str,
    ) -> list[LogEvent]:
        if target_agent_id == "agent_1":
            end_index = self._first_index(
                events,
                {
                    "agent_1_handoff",
                    "agent_1_case_state",
                    "agent_2",
                    "agent_2_handoff",
                    "agent_2_case_state",
                    "agent_3",
                    "agent_3_handoff",
                    "agent_3_case_state",
                },
            )
            selected = self._slice_with_handoff_tail(events, 0, end_index, {"agent_1_handoff", "agent_1_case_state"})
            allowed = {"borrower", "agent_1", "agent_1_handoff", "agent_1_case_state"}
            return [event for event in selected if (event.actor or "") in allowed]

        if target_agent_id == "agent_2":
            start_index = self._first_index(events, {"agent_1_handoff", "agent_1_case_state", "agent_2"})
            if start_index is None:
                return [event for event in events if (event.actor or "") in {"borrower", "agent_2"}]
            end_index = self._first_index(
                events[start_index:],
                {"agent_2_handoff", "agent_2_case_state", "agent_3", "agent_3_handoff", "agent_3_case_state"},
            )
            absolute_end_index = start_index + end_index if end_index is not None else None
            selected = self._slice_with_handoff_tail(
                events,
                start_index,
                absolute_end_index,
                {"agent_2_handoff", "agent_2_case_state"},
            )
            allowed = {
                "borrower",
                "agent_2",
                "agent_1_handoff",
                "agent_1_case_state",
                "agent_2_handoff",
                "agent_2_case_state",
            }
            return [event for event in selected if (event.actor or "") in allowed]

        if target_agent_id == "agent_3":
            start_index = self._first_index(events, {"agent_2_handoff", "agent_2_case_state", "agent_3"})
            if start_index is None:
                return events
            selected = events[start_index:]
            allowed = {"borrower", "agent_3", "agent_2_handoff", "agent_2_case_state"}
            return [event for event in selected if (event.actor or "") in allowed]

        return events

    def _first_index(self, events: list[LogEvent], actors: set[str]) -> int | None:
        for index, event in enumerate(events):
            if (event.actor or "") in actors:
                return index
        return None

    def _slice_with_handoff_tail(
        self,
        events: list[LogEvent],
        start_index: int,
        end_index: int | None,
        tail_actors: set[str],
    ) -> list[LogEvent]:
        if end_index is None:
            return events[start_index:]

        selected = events[start_index:end_index]
        index = end_index
        while index < len(events) and (events[index].actor or "") in tail_actors:
            selected.append(events[index])
            index += 1
        return selected
