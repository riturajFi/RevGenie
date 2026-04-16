from __future__ import annotations

import json
import os

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from evals.logging_service.logger import get_logs
from evals.judge_service.service import JudgeService
from evals.judgment_management_service.service import (
    JudgmentRecord,
    JudgmentRecordService,
    StoredJudgeResult,
)
from evals.meta_eval_management_service.service import (
    EvidenceBundle,
    ExperimentCorrectnessAnalysis,
    ExperimentValidationAnalysis,
    MetaEvalMetricAction,
    MetaEvalRunRecord,
    MetaEvalRunRecordService,
    ValidationDecision,
)
from evals.metrics_management_service.service import MetricDefinition, MetricsRegistry
from evals.policy_context import get_company_policy_text, get_compliance_rules_text

MAX_NEW_METRICS_PER_META_EVAL = 3
DEFAULT_META_EVAL_VALIDATION_EXPERIMENT_COUNT = 2

class MetaEvalProposalDraft(BaseModel):
    correctness_analysis: list[ExperimentCorrectnessAnalysis]
    metric_actions: list[MetaEvalMetricAction]
    updated_metrics_json: list[MetricDefinition]
    metrics_diff_summary: str
    why_this_change: str
    expected_improvement: str


class ExperimentValidationDraft(BaseModel):
    experiment_id: str
    winner: str
    reason: str
    evidence: EvidenceBundle


class ValidationDecisionDraft(BaseModel):
    decision: str
    reason: str
    experiment_results: list[ExperimentValidationDraft]

class ValidationExperimentContext(BaseModel):
    experiment_id: str
    transcript: str
    old_judgment: StoredJudgeResult
    candidate_judgment: StoredJudgeResult

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
        self.model_name = model or os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    def judge(
        self,
        before_experiment_id: str,
        after_experiment_id: str,
        metrics_key: str,
        lender_id: str | None = None,
        force_activate: bool = True,
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
        proposal = self._cap_metric_expansion(
            proposal=proposal,
            active_metrics=active_metrics.metrics,
        )

        candidate_metrics_version = self.metrics_registry.create_metrics_version(
            metrics_key=metrics_key,
            metrics=proposal.updated_metrics_json,
            diff_summary=proposal.metrics_diff_summary,
        )

        validation_experiment_ids = self._select_validation_experiment_ids(
            exclude_ids=[before_experiment_id, after_experiment_id],
        )
        validation_contexts = self._build_validation_contexts(
            experiment_ids=validation_experiment_ids,
            metrics_key=metrics_key,
            lender_id=lender_id,
            old_metrics_version_id=active_metrics.version_id,
            candidate_metrics_version_id=candidate_metrics_version.version_id,
        )

        old_validation_judgments = [item.old_judgment for item in validation_contexts]
        candidate_validation_judgments = [item.candidate_judgment for item in validation_contexts]

        validation = self._validate_candidate_metrics(
            before_transcript=before_transcript,
            after_transcript=after_transcript,
            old_metrics=active_metrics.model_dump(),
            candidate_metrics=candidate_metrics_version.model_dump(),
            old_validation_judgments=old_validation_judgments,
            candidate_validation_judgments=candidate_validation_judgments,
            correctness_analysis=proposal.correctness_analysis,
            metric_actions=proposal.metric_actions,
            company_policy=company_policy,
        )

        normalized_decision = self._normalize_decision(validation.decision)
        compliance_gate_reason = self._detect_compliance_regression(
            old_validation_judgments=old_validation_judgments,
            candidate_validation_judgments=candidate_validation_judgments,
            old_metrics=active_metrics.metrics,
            candidate_metrics=candidate_metrics_version.metrics,
        )
        if compliance_gate_reason is not None:
            normalized_decision = "REJECT"

        activation_status = "inactive"
        if normalized_decision == "ADOPT" and force_activate:
            self.metrics_registry.activate_version(metrics_key, candidate_metrics_version.version_id)
            activation_status = "active"
        elif normalized_decision == "REJECT":
            activation_status = "rejected"

        validation_record = ValidationDecision(
            decision=normalized_decision,
            reason=compliance_gate_reason or validation.reason,
            experiment_results=self._merge_validation_results(
                validation.experiment_results,
                old_validation_judgments,
                candidate_validation_judgments,
            ),
        )

        return self.meta_eval_run_service.create_run(
            before_experiment_id=before_experiment_id,
            after_experiment_id=after_experiment_id,
            validation_experiment_ids=validation_experiment_ids,
            metrics_key=metrics_key,
            lender_id=lender_id,
            old_metrics_version=active_metrics.version_id,
            candidate_metrics_version=candidate_metrics_version.version_id,
            correctness_analysis=proposal.correctness_analysis,
            metric_actions=proposal.metric_actions,
            candidate_metrics=proposal.updated_metrics_json,
            metrics_diff_summary=proposal.metrics_diff_summary,
            why_this_change=proposal.why_this_change,
            expected_improvement=proposal.expected_improvement,
            old_validation_judgments=old_validation_judgments,
            candidate_validation_judgments=candidate_validation_judgments,
            validation_decision=validation_record,
            activation_status=activation_status,
        )

    def apply_meta_change(
        self,
        before_experiment_id: str,
        after_experiment_id: str,
        metrics_key: str,
        lender_id: str | None = None,
        force_activate: bool = True,
    ) -> MetaEvalRunRecord:
        return self.judge(
            before_experiment_id=before_experiment_id,
            after_experiment_id=after_experiment_id,
            metrics_key=metrics_key,
            lender_id=lender_id,
            force_activate=force_activate,
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
        llm = ChatOpenAI(model=self.model_name, temperature=0)
        chain = prompt | llm.with_structured_output(MetaEvalProposalDraft)
        return chain.invoke(
            {
                "system_prompt": (
                    "You are the meta evaluator for a collections evaluation loop. "
                    "Use the global compliance rules and the company policy as the source of truth. "
                    "Treat the before and after transcripts as first-class evidence. "
                    "Determine whether the evaluator judge was correct for each experiment. "
                    "Keep changes minimal and surgical. Prefer keeping or rewriting existing metrics over adding new ones. "
                    "Add at most 3 new metrics in a single proposal, and prefer 0-2 new metrics unless a blind spot clearly requires more. "
                    "Then decide for each metric whether it should stay, be deleted, be added, or be rewritten. "
                    "Return a full candidate metrics list with policy_references for every metric. "
                    "Return strict JSON only."
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

    def _validate_candidate_metrics(
        self,
        before_transcript: str,
        after_transcript: str,
        old_metrics: dict,
        candidate_metrics: dict,
        old_validation_judgments: list[StoredJudgeResult],
        candidate_validation_judgments: list[StoredJudgeResult],
        correctness_analysis: list[ExperimentCorrectnessAnalysis],
        metric_actions: list[MetaEvalMetricAction],
        company_policy: str,
    ) -> ValidationDecisionDraft:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{human_prompt}"),
            ]
        )
        llm = ChatOpenAI(model=self.model_name, temperature=0)
        chain = prompt | llm.with_structured_output(ValidationDecisionDraft)
        return chain.invoke(
            {
                "system_prompt": (
                    "You are validating candidate metrics for a collections evaluator judge. "
                    "Use the global compliance rules and the company policy as the source of truth. "
                    "Compare old-metrics judgments against candidate-metrics judgments on the same transcripts. "
                    "Adopt the candidate only if it is clearly better. "
                    "If evidence is mixed or unclear, reject. "
                    "Return strict JSON only."
                ),
                "human_prompt": self._build_validation_prompt(
                    before_transcript=before_transcript,
                    after_transcript=after_transcript,
                    old_metrics=old_metrics,
                    candidate_metrics=candidate_metrics,
                    old_validation_judgments=old_validation_judgments,
                    candidate_validation_judgments=candidate_validation_judgments,
                    correctness_analysis=correctness_analysis,
                    metric_actions=metric_actions,
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
            "Return JSON with:\n"
            "- correctness_analysis: one item per experiment containing judge_got_right, judge_got_wrong, judge_missed, and evidence\n"
            "- metric_actions: one item per metric decision with action keep|delete|add|rewrite, rationale, policy_references, proposed_metric when relevant, and evidence\n"
            "- updated_metrics_json: the full candidate metrics list\n"
            "- metrics_diff_summary\n"
            "- why_this_change\n"
            "- expected_improvement\n"
            "Every candidate metric in updated_metrics_json must include policy_references.\n"
            f"Do not add more than {MAX_NEW_METRICS_PER_META_EVAL} new metrics beyond the active metrics list.\n"
            "Prefer 0-2 new metrics. If an existing metric can be rewritten instead of adding a new one, rewrite it.\n"
            "Preserve existing metric_ids for kept or rewritten metrics. Use new metric_ids only for truly new metrics."
        )

    def _build_validation_prompt(
        self,
        before_transcript: str,
        after_transcript: str,
        old_metrics: dict,
        candidate_metrics: dict,
        old_validation_judgments: list[StoredJudgeResult],
        candidate_validation_judgments: list[StoredJudgeResult],
        correctness_analysis: list[ExperimentCorrectnessAnalysis],
        metric_actions: list[MetaEvalMetricAction],
        company_policy: str,
    ) -> str:
        return (
            f"Global compliance rules:\n{get_compliance_rules_text()}\n\n"
            f"Company policy:\n{company_policy or 'No lender policy found.'}\n\n"
            f"Old metrics version JSON:\n{json.dumps(old_metrics, indent=2)}\n\n"
            f"Candidate metrics version JSON:\n{json.dumps(candidate_metrics, indent=2)}\n\n"
            f"Correctness analysis:\n{json.dumps([item.model_dump() for item in correctness_analysis], indent=2)}\n\n"
            f"Metric actions:\n{json.dumps([item.model_dump() for item in metric_actions], indent=2)}\n\n"
            f"Before transcript:\n{before_transcript}\n\n"
            f"After transcript:\n{after_transcript}\n\n"
            f"Old validation judgments:\n{json.dumps([item.model_dump() for item in old_validation_judgments], indent=2)}\n\n"
            f"Candidate validation judgments:\n{json.dumps([item.model_dump() for item in candidate_validation_judgments], indent=2)}\n\n"
            "Use the validation judgments as held-out evidence. Prefer REJECT if the candidate is not clearly better.\n"
            "If the candidate introduces any compliance regression or makes compliance enforcement weaker, reject it.\n"
            "Return JSON with:\n"
            '- decision: "ADOPT" or "REJECT"\n'
            "- reason\n"
            "- experiment_results: one item per experiment with winner, reason, and evidence\n"
        )

    def _rerun_validation_judgments(
        self,
        experiment_ids: list[str],
        metrics_key: str,
        metrics_version_id: str,
        lender_id: str | None,
    ) -> list[StoredJudgeResult]:
        judgments: list[StoredJudgeResult] = []
        for experiment_id in experiment_ids:
            result = self.judge_service.judge_experiment(
                experiment_id=experiment_id,
                metrics_key=metrics_key,
                lender_id=lender_id,
                metrics_version_id=metrics_version_id,
                persist=False,
            )
            judgments.append(StoredJudgeResult.model_validate(result.model_dump()))
        return judgments

    def _merge_validation_results(
        self,
        validation_drafts: list[ExperimentValidationDraft],
        old_validation_judgments: list[StoredJudgeResult],
        candidate_validation_judgments: list[StoredJudgeResult],
    ) -> list[ExperimentValidationAnalysis]:
        old_by_experiment = {item.experiment_id: item for item in old_validation_judgments}
        candidate_by_experiment = {item.experiment_id: item for item in candidate_validation_judgments}
        results: list[ExperimentValidationAnalysis] = []
        for draft in validation_drafts:
            results.append(
                ExperimentValidationAnalysis(
                    experiment_id=draft.experiment_id,
                    winner=self._normalize_winner(draft.winner),
                    reason=draft.reason,
                    old_judgment=old_by_experiment[draft.experiment_id],
                    candidate_judgment=candidate_by_experiment[draft.experiment_id],
                    evidence=draft.evidence,
                )
            )
        return results

    def _get_or_build_record(self, experiment_id: str) -> JudgmentRecord:
        record = self.judgment_record_service.get_record(experiment_id)
        if record is not None and record.judgment is not None:
            return record

        judgment = self.judge_service.get_judgment(experiment_id)
        return self.judgment_record_service.save_judgment_result(judgment)

    def _select_validation_experiment_ids(
        self,
        exclude_ids: list[str],
        limit: int = DEFAULT_META_EVAL_VALIDATION_EXPERIMENT_COUNT,
    ) -> list[str]:
        excluded = set(exclude_ids)
        selected: list[str] = []

        for record in reversed(self.judgment_record_service.list_records()):
            if record.judgment is None:
                continue
            if record.experiment_id in excluded:
                continue
            selected.append(record.experiment_id)
            if len(selected) >= limit:
                break

        return selected

    def _build_validation_contexts(
        self,
        experiment_ids: list[str],
        metrics_key: str,
        lender_id: str | None,
        old_metrics_version_id: str,
        candidate_metrics_version_id: str,
    ) -> list[ValidationExperimentContext]:
        if not experiment_ids:
            return []

        old_judgments = self._rerun_validation_judgments(
            experiment_ids=experiment_ids,
            metrics_key=metrics_key,
            metrics_version_id=old_metrics_version_id,
            lender_id=lender_id,
        )
        candidate_judgments = self._rerun_validation_judgments(
            experiment_ids=experiment_ids,
            metrics_key=metrics_key,
            metrics_version_id=candidate_metrics_version_id,
            lender_id=lender_id,
        )

        contexts: list[ValidationExperimentContext] = []
        for experiment_id, old_judgment, candidate_judgment in zip(
            experiment_ids,
            old_judgments,
            candidate_judgments,
            strict=True,
        ):
            contexts.append(
                ValidationExperimentContext(
                    experiment_id=experiment_id,
                    transcript=self._load_transcript(experiment_id),
                    old_judgment=old_judgment,
                    candidate_judgment=candidate_judgment,
                )
            )

        return contexts

    def _detect_compliance_regression(
        self,
        old_validation_judgments: list[StoredJudgeResult],
        candidate_validation_judgments: list[StoredJudgeResult],
        old_metrics: list[MetricDefinition],
        candidate_metrics: list[MetricDefinition],
    ) -> str | None:
        compliance_metric_ids = self._get_compliance_metric_ids(old_metrics) | self._get_compliance_metric_ids(
            candidate_metrics
        )
        if not compliance_metric_ids:
            return None

        old_by_experiment = {item.experiment_id: item for item in old_validation_judgments}
        candidate_by_experiment = {item.experiment_id: item for item in candidate_validation_judgments}

        for experiment_id, old_judgment in old_by_experiment.items():
            candidate_judgment = candidate_by_experiment.get(experiment_id)
            if candidate_judgment is None:
                continue

            old_scores = {score.metric_id: score for score in old_judgment.scores}
            candidate_scores = {score.metric_id: score for score in candidate_judgment.scores}

            for metric_id in compliance_metric_ids:
                old_score = old_scores.get(metric_id)
                candidate_score = candidate_scores.get(metric_id)
                if old_score is None or candidate_score is None:
                    continue
                if candidate_score.score < old_score.score:
                    return (
                        "Rejected due to compliance regression on "
                        f"{experiment_id}: metric {metric_id} dropped from {old_score.score} to {candidate_score.score}."
                    )

        return None

    def _get_compliance_metric_ids(self, metrics: list[MetricDefinition]) -> set[str]:
        compliance_metric_ids: set[str] = set()
        for metric in metrics:
            search_blob = " ".join(
                [
                    metric.metric_id,
                    metric.name,
                    metric.description,
                    " ".join(metric.policy_references),
                ]
            ).lower()
            if any(
                token in search_blob
                for token in (
                    "compliance",
                    "policy",
                    "disclosure",
                    "identity",
                    "stop_contact",
                    "stop-contact",
                    "harassment",
                    "consent",
                )
            ):
                compliance_metric_ids.add(metric.metric_id)
        return compliance_metric_ids

    def _normalize_decision(self, decision: str) -> str:
        normalized = decision.strip().upper()
        return "ADOPT" if normalized == "ADOPT" else "REJECT"

    def _normalize_winner(self, winner: str) -> str:
        normalized = winner.strip().upper()
        if normalized in {"OLD", "CANDIDATE", "TIE"}:
            return normalized
        return "TIE"

    def _load_transcript(self, experiment_id: str) -> str:
        events = get_logs(experiment_id)
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
            if action.action == "add" and proposed_metric is not None:
                if proposed_metric.metric_id in dropped_new_metric_ids:
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
