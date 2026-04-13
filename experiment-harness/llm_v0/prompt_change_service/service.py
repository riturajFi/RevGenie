from __future__ import annotations

import json
import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from experiment_harness.logging_service.logger import get_logs
from experiment_harness.prompt_management_service.prompt_storage import (
    PromptStorageService,
    json_prompt_storage_service,
)
from judge_service.service import JudgeService
from proposer_prompt_management_service.service import ProposerPromptManager


class PromptChangeApplyRequest(BaseModel):
    experiment_id: str
    target_agent_id: str
    force_activate: bool = True


class PromptChangeDraft(BaseModel):
    new_prompt_text: str
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
        model: str | None = None,
    ) -> None:
        self.prompt_service = prompt_service or json_prompt_storage_service
        self.judge_service = judge_service or JudgeService()
        self.proposer_prompt_manager = proposer_prompt_manager or ProposerPromptManager()
        self.model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def apply_change(
        self,
        experiment_id: str,
        target_agent_id: str,
        force_activate: bool = True,
    ) -> PromptChangeApplyResult:
        active_prompt = self.prompt_service.get_active_prompt(target_agent_id)
        judge_result = self.judge_service.get_judgment(experiment_id)
        transcript = self._load_transcript(experiment_id)
        draft = self._propose_prompt_change(
            current_prompt=active_prompt.prompt_text,
            judge_result=judge_result,
            transcript=transcript,
        )
        new_version = self.prompt_service.create_prompt_version(
            agent_id=target_agent_id,
            prompt_text=draft.new_prompt_text,
            parent_version_id=active_prompt.version_id,
            diff_summary=draft.diff_summary,
        )
        activation_status = "inactive"
        if force_activate:
            self.prompt_service.activate_version(target_agent_id, new_version.version_id)
            activation_status = "active"
        return PromptChangeApplyResult(
            agent_id=target_agent_id,
            old_version_id=active_prompt.version_id,
            new_version_id=new_version.version_id,
            diff_summary=draft.diff_summary,
            activation_status=activation_status,
        )

    def _propose_prompt_change(
        self,
        current_prompt: str,
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
                    current_prompt=current_prompt,
                    judge_result=judge_result.model_dump(),
                    transcript=transcript,
                ),
            }
        )

    def _build_human_prompt(
        self,
        current_prompt: str,
        judge_result: dict,
        transcript: str,
    ) -> str:
        return (
            f"Current prompt:\n{current_prompt}\n\n"
            f"Judge output:\n{json.dumps(judge_result, indent=2)}\n\n"
            f"Transcript:\n{transcript}\n\n"
            "Return JSON with:\n"
            "- new_prompt_text\n"
            "- diff_summary\n"
            "- why_this_change\n"
        )

    def _load_transcript(self, experiment_id: str) -> str:
        events = get_logs(experiment_id)
        return "\n".join(
            f"[{event.created_at}] {event.actor or 'unknown'}: {event.message_text}"
            for event in events
        )
