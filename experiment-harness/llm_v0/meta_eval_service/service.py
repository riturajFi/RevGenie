from __future__ import annotations

import json
import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from experiment_harness.logging_service.logger import get_logs
from judge_service.service import JudgeService
from metrics_management_service.service import MetricDefinition, MetricsRegistry
from proposer_prompt_management_service.service import ProposerPromptManager


class MetaEvalDraft(BaseModel):
    updated_metrics_json: list[MetricDefinition]
    metrics_diff_summary: str
    updated_proposer_prompt: str
    proposer_prompt_diff_summary: str
    why_this_change: str
    expected_improvement: str


class MetaEvaluatorApplyResult(BaseModel):
    before_experiment_id: str
    after_experiment_id: str
    old_metrics_version: str
    new_metrics_version: str
    old_proposer_prompt_version: str
    new_proposer_prompt_version: str
    metrics_diff_summary: str
    proposer_prompt_diff_summary: str
    activation_status: str


class MetaEvaluatorService:
    def __init__(
        self,
        judge_service: JudgeService | None = None,
        metrics_registry: MetricsRegistry | None = None,
        proposer_prompt_manager: ProposerPromptManager | None = None,
        model: str | None = None,
    ) -> None:
        self.judge_service = judge_service or JudgeService()
        self.metrics_registry = metrics_registry or MetricsRegistry()
        self.proposer_prompt_manager = proposer_prompt_manager or ProposerPromptManager()
        self.model_name = model or os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    def apply_meta_change(
        self,
        before_experiment_id: str,
        after_experiment_id: str,
        metrics_key: str,
        force_activate: bool = True,
    ) -> MetaEvaluatorApplyResult:
        before_judgment = self.judge_service.get_judgment(before_experiment_id)
        after_judgment = self.judge_service.get_judgment(after_experiment_id)
        before_transcript = self._load_transcript(before_experiment_id)
        after_transcript = self._load_transcript(after_experiment_id)
        active_metrics = self.metrics_registry.get_active_metrics(metrics_key)
        active_proposer_prompt = self.proposer_prompt_manager.get_active_prompt()
        draft = self._propose_meta_change(
            before_judgment=before_judgment.model_dump(),
            after_judgment=after_judgment.model_dump(),
            before_transcript=before_transcript,
            after_transcript=after_transcript,
            active_metrics=active_metrics.model_dump(),
            active_proposer_prompt=active_proposer_prompt.prompt_text,
        )
        new_metrics_version = self.metrics_registry.create_metrics_version(
            metrics_key=metrics_key,
            metrics=draft.updated_metrics_json,
            diff_summary=draft.metrics_diff_summary,
        )
        new_proposer_prompt_version = self.proposer_prompt_manager.create_prompt_version(
            prompt_text=draft.updated_proposer_prompt,
            diff_summary=draft.proposer_prompt_diff_summary,
        )
        activation_status = "inactive"
        if force_activate:
            self.metrics_registry.activate_version(metrics_key, new_metrics_version.version_id)
            self.proposer_prompt_manager.activate_version(new_proposer_prompt_version.version_id)
            activation_status = "active"
        return MetaEvaluatorApplyResult(
            before_experiment_id=before_experiment_id,
            after_experiment_id=after_experiment_id,
            old_metrics_version=active_metrics.version_id,
            new_metrics_version=new_metrics_version.version_id,
            old_proposer_prompt_version=active_proposer_prompt.version_id,
            new_proposer_prompt_version=new_proposer_prompt_version.version_id,
            metrics_diff_summary=draft.metrics_diff_summary,
            proposer_prompt_diff_summary=draft.proposer_prompt_diff_summary,
            activation_status=activation_status,
        )

    def _propose_meta_change(
        self,
        before_judgment: dict,
        after_judgment: dict,
        before_transcript: str,
        after_transcript: str,
        active_metrics: dict,
        active_proposer_prompt: str,
    ) -> MetaEvalDraft:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{human_prompt}"),
            ]
        )
        llm = ChatOpenAI(model=self.model_name, temperature=0)
        chain = prompt | llm.with_structured_output(MetaEvalDraft)
        return chain.invoke(
            {
                "system_prompt": (
                    "You are the meta evaluator for a collections evaluation loop. "
                    "Compare before and after judged runs and improve only the judge metrics and proposer prompt. "
                    "Return strict JSON only."
                ),
                "human_prompt": self._build_human_prompt(
                    before_judgment=before_judgment,
                    after_judgment=after_judgment,
                    before_transcript=before_transcript,
                    after_transcript=after_transcript,
                    active_metrics=active_metrics,
                    active_proposer_prompt=active_proposer_prompt,
                ),
            }
        )

    def _build_human_prompt(
        self,
        before_judgment: dict,
        after_judgment: dict,
        before_transcript: str,
        after_transcript: str,
        active_metrics: dict,
        active_proposer_prompt: str,
    ) -> str:
        return (
            f"Before judgment:\n{json.dumps(before_judgment, indent=2)}\n\n"
            f"After judgment:\n{json.dumps(after_judgment, indent=2)}\n\n"
            f"Before transcript:\n{before_transcript}\n\n"
            f"After transcript:\n{after_transcript}\n\n"
            f"Active metrics JSON:\n{json.dumps(active_metrics, indent=2)}\n\n"
            f"Active proposer prompt:\n{active_proposer_prompt}\n\n"
            "Return JSON with:\n"
            "- updated_metrics_json\n"
            "- metrics_diff_summary\n"
            "- updated_proposer_prompt\n"
            "- proposer_prompt_diff_summary\n"
            "- why_this_change\n"
            "- expected_improvement\n"
        )

    def _load_transcript(self, experiment_id: str) -> str:
        events = get_logs(experiment_id)
        return "\n".join(
            f"[{event.created_at}] {event.actor or 'unknown'}: {event.message_text}"
            for event in events
        )
