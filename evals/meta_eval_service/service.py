from __future__ import annotations

import json
import os

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.services.llm_factory import build_chat_llm
from evals.judge_service.service import JudgeService
from evals.judgment_management_service.service import JudgmentRecord, JudgmentRecordService
from evals.logging_service import TranscriptLoggingService
from evals.meta_eval_management_service.service import (
    ExperimentCorrectnessAnalysis,
    MetaEvalMetricAction,
    MetaEvalRunRecord,
    MetaEvalRunRecordService,
)
from evals.metrics_management_service.service import MetricDefinition, MetricsRegistry
from evals.policy_context import get_company_policy_text, get_compliance_rules_text

MAX_NEW_METRICS_PER_META_EVAL = 3


class MetaEvalProposalDraft(BaseModel):
    correctness_analysis: list[ExperimentCorrectnessAnalysis] = Field(default_factory=list)
    metric_actions: list[MetaEvalMetricAction] = Field(default_factory=list)
    updated_metrics_json: list[MetricDefinition] = Field(default_factory=list)
    metrics_diff_summary: str = ""
    why_this_change: str = ""
    expected_improvement: str = ""


class MetaEvaluatorService:
    def __init__(
        self,
        judge_service: JudgeService | None = None,
        judgment_record_service: JudgmentRecordService | None = None,
        metrics_registry: MetricsRegistry | None = None,
        meta_eval_run_service: MetaEvalRunRecordService | None = None,
        model: str | None = None,
    ) -> None:
        self.judge_service = judge_service or JudgeService()
        self.judgment_record_service = judgment_record_service or JudgmentRecordService()
        self.metrics_registry = metrics_registry or MetricsRegistry()
        self.meta_eval_run_service = meta_eval_run_service or MetaEvalRunRecordService()
        self.logging_service = TranscriptLoggingService()
        self.model_name = (
            model
            or os.getenv("LLM_JUDGE_MODEL")
            or os.getenv("LLM_MODEL")
            or os.getenv("OPENAI_JUDGE_MODEL")
            or os.getenv("OPENAI_MODEL")
            or os.getenv("CLAUDE_MODEL")
            or os.getenv("ANTHROPIC_MODEL")
        )

    def judge(
        self,
        before_experiment_id: str,
        after_experiment_id: str,
        metrics_key: str,
        lender_id: str | None = None,
    ) -> MetaEvalRunRecord:
        before_record = self._get_or_build_record(before_experiment_id)
        after_record = self._get_or_build_record(after_experiment_id)
        before_transcript = self._load_transcript(before_experiment_id)
        after_transcript = self._load_transcript(after_experiment_id)
        active_metrics = self.metrics_registry.get_active_metrics(metrics_key)
        company_policy = get_company_policy_text(lender_id)

        proposal = self._propose_candidate_metrics(
            before_record=before_record,
            after_record=after_record,
            before_transcript=before_transcript,
            after_transcript=after_transcript,
            active_metrics=active_metrics.model_dump(),
            company_policy=company_policy,
        )
        if not proposal.updated_metrics_json:
            proposal.updated_metrics_json = active_metrics.metrics
        if not proposal.metrics_diff_summary:
            proposal.metrics_diff_summary = "No metric diff summary returned."
        if not proposal.why_this_change:
            proposal.why_this_change = "No rationale returned."
        if not proposal.expected_improvement:
            proposal.expected_improvement = "No expected improvement returned."
        proposal = self._cap_metric_expansion(
            proposal=proposal,
            active_metrics=active_metrics.metrics,
        )

        return self.meta_eval_run_service.create_run(
            before_experiment_id=before_experiment_id,
            after_experiment_id=after_experiment_id,
            metrics_key=metrics_key,
            lender_id=lender_id,
            old_metrics_version=active_metrics.version_id,
            correctness_analysis=proposal.correctness_analysis,
            metric_actions=proposal.metric_actions,
            candidate_metrics=proposal.updated_metrics_json,
            metrics_diff_summary=proposal.metrics_diff_summary,
            why_this_change=proposal.why_this_change,
            expected_improvement=proposal.expected_improvement,
        )

    def apply_meta_change(
        self,
        before_experiment_id: str,
        after_experiment_id: str,
        metrics_key: str,
        lender_id: str | None = None,
    ) -> MetaEvalRunRecord:
        return self.judge(
            before_experiment_id=before_experiment_id,
            after_experiment_id=after_experiment_id,
            metrics_key=metrics_key,
            lender_id=lender_id,
        )

    def get_run(self, run_id: str) -> MetaEvalRunRecord | None:
        return self.meta_eval_run_service.get_run(run_id)

    def list_runs(self) -> list[MetaEvalRunRecord]:
        return self.meta_eval_run_service.list_runs()

    def _propose_candidate_metrics(
        self,
        before_record: JudgmentRecord,
        after_record: JudgmentRecord,
        before_transcript: str,
        after_transcript: str,
        active_metrics: dict,
        company_policy: str,
    ) -> MetaEvalProposalDraft:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{human_prompt}"),
            ]
        )
        llm = build_chat_llm(
            model=self.model_name,
            temperature=0,
            model_env_keys=("OPENAI_JUDGE_MODEL", "OPENAI_MODEL", "CLAUDE_MODEL", "ANTHROPIC_MODEL"),
        )
        chain = prompt | llm.with_structured_output(MetaEvalProposalDraft)
        return chain.invoke(
            {
                "system_prompt": (
                    "You are a strict meta evaluator. "
                    "Return JSON only. "
                    "Return one complete object. "
                    "Never return {}. "
                    "Never omit required keys. "
                    "Required top-level keys are: correctness_analysis, metric_actions, updated_metrics_json, metrics_diff_summary, why_this_change, expected_improvement. "
                    "correctness_analysis must be an array. "
                    "metric_actions must be an array. "
                    "updated_metrics_json must be an array. "
                    "metrics_diff_summary must be a string. "
                    "why_this_change must be a string. "
                    "expected_improvement must be a string. "
                    "Use the compliance rules, company policy, before record, after record, and both transcripts as evidence. "
                    "Keep changes minimal. Prefer keep or rewrite over add. "
                    "Every candidate metric must include policy_references."
                ),
                "human_prompt": self._build_proposal_prompt(
                    before_record=before_record,
                    after_record=after_record,
                    before_transcript=before_transcript,
                    after_transcript=after_transcript,
                    active_metrics=active_metrics,
                    company_policy=company_policy,
                ),
            }
        )

    def _build_proposal_prompt(
        self,
        before_record: JudgmentRecord,
        after_record: JudgmentRecord,
        before_transcript: str,
        after_transcript: str,
        active_metrics: dict,
        company_policy: str,
    ) -> str:
        return (
            f"Global compliance rules:\n{get_compliance_rules_text()}\n\n"
            f"Company policy:\n{company_policy or 'No lender policy found.'}\n\n"
            f"Active metrics version JSON:\n{json.dumps(active_metrics, indent=2)}\n\n"
            f"Before experiment record:\n{json.dumps(before_record.model_dump(), indent=2)}\n\n"
            f"Before transcript:\n{before_transcript}\n\n"
            f"After experiment record:\n{json.dumps(after_record.model_dump(), indent=2)}\n\n"
            f"After transcript:\n{after_transcript}\n\n"
            "Return one complete JSON object.\n"
            "Do not return {}.\n"
            "Do not omit any required key.\n"
            "Required keys:\n"
            "- correctness_analysis\n"
            "- metric_actions\n"
            "- updated_metrics_json\n"
            "- metrics_diff_summary\n"
            "- why_this_change\n"
            "- expected_improvement\n"
            "correctness_analysis must contain one item for the before experiment and one item for the after experiment.\n"
            "metric_actions must contain one item per keep, delete, add, or rewrite decision.\n"
            "updated_metrics_json must be the full candidate metrics list, not a diff.\n"
            "Every candidate metric in updated_metrics_json must include policy_references.\n"
            f"Do not add more than {MAX_NEW_METRICS_PER_META_EVAL} new metrics beyond the active metrics list.\n"
            "Prefer 0-2 new metrics. If an existing metric can be rewritten instead of adding a new one, rewrite it.\n"
            "Preserve existing metric_ids for kept or rewritten metrics. Use new metric_ids only for truly new metrics.\n"
        )

    def _get_or_build_record(self, experiment_id: str) -> JudgmentRecord:
        record = self.judgment_record_service.get_record(experiment_id)
        if record is not None and record.judgment is not None:
            return record

        judgment = self.judge_service.get_judgment(experiment_id)
        return self.judgment_record_service.save_judgment_result(judgment)

    def _load_transcript(self, experiment_id: str) -> str:
        events = self.logging_service.get_logs(experiment_id)
        return "\n".join(
            f"[{event.created_at}] {event.actor or 'unknown'}: {event.message_text}"
            for event in events
        )

    def _cap_metric_expansion(
        self,
        proposal: MetaEvalProposalDraft,
        active_metrics: list[MetricDefinition],
    ) -> MetaEvalProposalDraft:
        active_metric_ids = {metric.metric_id for metric in active_metrics}
        kept_new_metric_ids: list[str] = []
        dropped_new_metric_ids: list[str] = []
        limited_metrics: list[MetricDefinition] = []

        for metric in proposal.updated_metrics_json:
            is_existing_metric = metric.metric_id in active_metric_ids
            if is_existing_metric:
                limited_metrics.append(metric)
                continue

            if metric.metric_id in kept_new_metric_ids:
                limited_metrics.append(metric)
                continue

            if len(kept_new_metric_ids) < MAX_NEW_METRICS_PER_META_EVAL:
                kept_new_metric_ids.append(metric.metric_id)
                limited_metrics.append(metric)
            else:
                dropped_new_metric_ids.append(metric.metric_id)

        if not dropped_new_metric_ids:
            return proposal

        limited_actions: list[MetaEvalMetricAction] = []
        for action in proposal.metric_actions:
            proposed_metric = action.proposed_metric
            if action.action == "add" and proposed_metric is not None and proposed_metric.metric_id in dropped_new_metric_ids:
                continue
            limited_actions.append(action)

        trim_note = (
            f" Proposal was capped to {MAX_NEW_METRICS_PER_META_EVAL} new metrics to keep the evaluator prompt small."
        )

        return proposal.model_copy(
            update={
                "metric_actions": limited_actions,
                "updated_metrics_json": limited_metrics,
                "metrics_diff_summary": f"{proposal.metrics_diff_summary}{trim_note}",
                "why_this_change": f"{proposal.why_this_change}{trim_note}",
            }
        )
