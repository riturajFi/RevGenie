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
    apply_change: bool
    instruction_line: str | None
    example_lines: list[str]
    diff_summary: str | None = None
    why_this_change: str | None = None


class PromptChangeApplyResult(BaseModel):
    agent_id: str
    old_version_id: str
    new_version_id: str
    diff_summary: str
    why_this_change: str
    activation_status: str


class PromptChangeProposer:
    PROPOSER_SYSTEM_PROMPT = """You are a surgical prompt patcher for a self-improving agent system.

Your job is not to rewrite the agent prompt.
Your job is not to expand coverage broadly.
Your job is not to restate policy.

Your job is to read:
- the current prompt
- the current prompt lines
- the judge result
- the target-agent transcript

Then produce the smallest useful patch for the single highest-value failure shown by the evidence.

You must use the sources in this order:
1. Judge result: primary source of what failed.
2. Transcript: proof of how the failure appeared in the conversation.
3. Current prompt lines: check whether the failure is already covered.
4. Current prompt text: use only for broader context if needed.

Patching rules:
- Patch only one failure per iteration.
- Prefer no change over a bad change.
- If the prompt already covers the failure clearly, return no patch.
- Do not rewrite the full prompt.
- Do not create new sections.
- Do not duplicate existing sections.
- Do not repeat or paraphrase existing rules.
- Do not add broad policy reminders.
- Do not add multiple unrelated fixes.
- Do not add verbose explanations.
- Do not add anything that increases prompt length more than necessary.
- More text is usually worse.
- Prompt pollution causes regression.

Allowed output shape:
- one new instruction line for the learned-rules section
- optionally one short example block
- nothing else

Hard limits:
- Add at most 1 instruction line.
- Add at most 1 example block.
- Example block may contain at most 3 lines.
- Total appended lines must be at most 5.
- Every added line must be short, specific, and testable.

What counts as a good patch:
- It addresses a failure that is visible in the judge result and transcript.
- It adds a narrow behavioral correction.
- It does not conflict with the existing prompt.
- It can be understood as an append-only learned patch.
- It improves precision without changing the base architecture of the prompt.

What counts as a bad patch:
- Rewriting the whole prompt.
- Recreating old sections.
- Adding many scenario variants.
- Adding generic compliance text already covered.
- Adding vague style advice.
- Adding long examples.
- Adding repeated hardship/refusal/verification prose when the base prompt already covers it.

Decision procedure:
1. Read the judge result and find the single most important concrete failure.
2. Verify that failure in the transcript.
3. Check whether the current prompt already covers it.
4. If already covered, return no patch.
5. If not covered, write one narrow instruction line.
6. Add an example only if the example is necessary to disambiguate the instruction.
7. Keep the patch minimal.

Return structured JSON only.

Field rules:
- instruction_line: a single prompt line string, or null
- example_lines: a list of 0 to 3 prompt lines
- diff_summary: one short sentence
- why_this_change: short explanation grounded in judge result + transcript
- apply_change: true or false

If apply_change is false:
- instruction_line must be null
- example_lines must be empty

Remember:
You are a patcher, not a rewriter.
Small precise fixes beat large clever rewrites."""

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
        append_prompt_lines = self._draft_to_prompt_lines(draft)
        new_prompt_lines = self._append_prompt_lines(active_prompt.prompt_lines, append_prompt_lines)
        diff_summary = self._resolve_diff_summary(draft, append_prompt_lines)
        why_this_change = self._resolve_why_this_change(draft, append_prompt_lines, target_agent_id)
        new_version = self.prompt_service.create_prompt_version(
            agent_id=target_agent_id,
            prompt_text=new_prompt_lines,
            parent_version_id=active_prompt.version_id,
            diff_summary=diff_summary,
        )
        activation_status = "inactive"
        if force_activate:
            self.prompt_service.activate_version(target_agent_id, new_version.version_id)
            activation_status = "active"
        result = PromptChangeApplyResult(
            agent_id=target_agent_id,
            old_version_id=active_prompt.version_id,
            new_version_id=new_version.version_id,
            diff_summary=diff_summary,
            why_this_change=why_this_change,
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
        return chain.invoke(
            {
                "system_prompt": self.PROPOSER_SYSTEM_PROMPT,
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
            "Task:\n"
            "Find the single highest-value failure from the judge output.\n"
            "Verify it in the transcript.\n"
            "Check whether the current prompt already covers it.\n"
            "If already covered, return apply_change=false.\n"
            "If not already covered, return one narrow patch only.\n\n"
            "Return JSON with fields:\n"
            "- apply_change\n"
            "- instruction_line\n"
            "- example_lines\n"
            "- diff_summary\n"
            "- why_this_change\n\n"
            "Hard limits:\n"
            "- instruction_line: at most 1 line\n"
            "- example_lines: at most 3 lines total\n"
            "- total added lines: at most 5\n"
            "- no new sections\n"
            "- no duplicated rules\n"
            "- no full prompt rewrites\n"
            "- no broad restatements\n"
            "- no patch if the failure is already covered\n"
        )

    def _append_prompt_lines(self, current_prompt_lines: list[str], append_prompt_lines: list[str]) -> list[str]:
        if not append_prompt_lines:
            return list(current_prompt_lines)

        merged = list(current_prompt_lines)
        if merged and merged[-1] != "":
            merged.append("")
        merged.extend(append_prompt_lines)
        return merged

    def _draft_to_prompt_lines(self, draft: PromptChangeDraft) -> list[str]:
        if not draft.apply_change:
            return []

        lines: list[str] = []
        if draft.instruction_line:
            lines.append(draft.instruction_line)
        lines.extend(draft.example_lines)
        return lines

    def _resolve_diff_summary(self, draft: PromptChangeDraft, append_prompt_lines: list[str]) -> str:
        provided = (draft.diff_summary or "").strip()
        if provided:
            return provided
        if append_prompt_lines:
            return "Applied focused learned-rule prompt patch."
        return "No prompt patch applied."

    def _resolve_why_this_change(
        self,
        draft: PromptChangeDraft,
        append_prompt_lines: list[str],
        target_agent_id: str,
    ) -> str:
        provided = (draft.why_this_change or "").strip()
        if provided:
            return provided
        if append_prompt_lines:
            return f"Applied a minimal fix for {target_agent_id} based on recent evaluation evidence."
        return "No high-confidence gap identified that required a prompt update."

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
