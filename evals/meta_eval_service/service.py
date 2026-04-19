from __future__ import annotations

import json
import os
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.services.llm_factory import build_chat_llm
from app.services.simulation_run_history import SimulationRunHistoryService
from evals.evaluation_config_service.service import EvaluationConfig, EvaluationConfigService, evaluation_config_service
from evals.logging_service import TranscriptLoggingService
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
DEFAULT_META_EVAL_VALIDATION_EXPERIMENT_COUNT = 3
DEFAULT_META_EVAL_VALIDATION_SET_PATH = Path(__file__).resolve().parents[2] / "data" / "evals" / "meta_eval_validation_set.json"
DEFAULT_EXPECTED_FAIL_SCORE_MAX = 6.0
DEFAULT_EXPECTED_PASS_SCORE_MIN = 8.0


class EvaluationConfigDraft(BaseModel):
    benchmark_scenario_ids: list[str] = Field(default_factory=list)
    benchmark_max_turns: int
    required_mean_score_delta: float
    required_win_rate: float
    require_compliance_non_regression: bool


class MetaEvalProposalDraft(BaseModel):
    correctness_analysis: list[ExperimentCorrectnessAnalysis]
    metric_actions: list[MetaEvalMetricAction]
    updated_metrics_json: list[MetricDefinition]
    metrics_diff_summary: str
    updated_evaluation_config_json: EvaluationConfigDraft
    evaluation_config_diff_summary: str
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
    scenario_id: str | None = None
    transcript: str
    old_judgment: StoredJudgeResult
    candidate_judgment: StoredJudgeResult
    target: "MetaEvalValidationTarget | None" = None


class MetaEvalValidationTarget(BaseModel):
    scenario_id: str
    purpose: str | None = None
    expected_verdict: str | None = None
    expected_fail_metrics: list[str] = Field(default_factory=list)
    expected_pass_metrics: list[str] = Field(default_factory=list)
    fail_score_max: float = DEFAULT_EXPECTED_FAIL_SCORE_MAX
    pass_score_min: float = DEFAULT_EXPECTED_PASS_SCORE_MIN


class MetaEvaluatorService:
    def __init__(
        self,
        judge_service: JudgeService | None = None,
        judgment_record_service: JudgmentRecordService | None = None,
        metrics_registry: MetricsRegistry | None = None,
        evaluation_config_service_: EvaluationConfigService | None = None,
        meta_eval_run_service: MetaEvalRunRecordService | None = None,
        run_history_service: SimulationRunHistoryService | None = None,
        model: str | None = None,
        validation_set_path: Path = DEFAULT_META_EVAL_VALIDATION_SET_PATH,
    ) -> None:
        self.judge_service = judge_service or JudgeService()
        self.judgment_record_service = judgment_record_service or JudgmentRecordService()
        self.metrics_registry = metrics_registry or MetricsRegistry()
        self.evaluation_config_service = evaluation_config_service_ or evaluation_config_service
        self.meta_eval_run_service = meta_eval_run_service or MetaEvalRunRecordService()
        self.run_history_service = run_history_service or SimulationRunHistoryService()
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
        self.validation_set_path = validation_set_path

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
        active_evaluation_config = self.evaluation_config_service.get_active()
        company_policy = get_company_policy_text(lender_id)

        proposal = self._propose_candidate_metrics(
            before_record=before_record,
            after_record=after_record,
            before_transcript=before_transcript,
            after_transcript=after_transcript,
            active_metrics=active_metrics.model_dump(),
            active_evaluation_config=active_evaluation_config.model_dump(),
            company_policy=company_policy,
        )
        proposal = self._cap_metric_expansion(
            proposal=proposal,
            active_metrics=active_metrics.metrics,
        )
        candidate_evaluation_config = self._sanitize_evaluation_config_proposal(
            proposal.updated_evaluation_config_json,
            active_config=active_evaluation_config,
        )

        candidate_metrics_version = self.metrics_registry.create_metrics_version(
            metrics_key=metrics_key,
            metrics=proposal.updated_metrics_json,
            diff_summary=proposal.metrics_diff_summary,
        )
        if self._same_evaluation_config(active_evaluation_config, candidate_evaluation_config):
            candidate_evaluation_config_version = active_evaluation_config
        else:
            candidate_evaluation_config_version = self.evaluation_config_service.create_version(
                benchmark_scenario_ids=candidate_evaluation_config.benchmark_scenario_ids,
                benchmark_max_turns=candidate_evaluation_config.benchmark_max_turns,
                required_mean_score_delta=candidate_evaluation_config.required_mean_score_delta,
                required_win_rate=candidate_evaluation_config.required_win_rate,
                require_compliance_non_regression=candidate_evaluation_config.require_compliance_non_regression,
                diff_summary=proposal.evaluation_config_diff_summary,
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
        validation_results, old_expectation_matches, candidate_expectation_matches, total_expectation_checks = (
            self._evaluate_expectation_backed_validation(validation_contexts)
        )
        compliance_gate_reason = self._detect_compliance_regression(
            old_validation_judgments=old_validation_judgments,
            candidate_validation_judgments=candidate_validation_judgments,
            old_metrics=active_metrics.metrics,
            candidate_metrics=candidate_metrics_version.metrics,
        )
        normalized_decision, validation_reason = self._decide_expectation_backed_validation(
            old_expectation_matches=old_expectation_matches,
            candidate_expectation_matches=candidate_expectation_matches,
            total_expectation_checks=total_expectation_checks,
            compliance_gate_reason=compliance_gate_reason,
        )

        activation_status = "inactive"
        if normalized_decision == "ADOPT" and force_activate:
            self.metrics_registry.activate_version(metrics_key, candidate_metrics_version.version_id)
            if candidate_evaluation_config_version.version_id != active_evaluation_config.version_id:
                self.evaluation_config_service.activate_version(candidate_evaluation_config_version.version_id)
            activation_status = "active"
        elif normalized_decision == "REJECT":
            activation_status = "rejected"

        validation_record = ValidationDecision(
            decision=normalized_decision,
            reason=validation_reason,
            old_expectation_matches=old_expectation_matches,
            candidate_expectation_matches=candidate_expectation_matches,
            total_expectation_checks=total_expectation_checks,
            experiment_results=validation_results,
        )

        return self.meta_eval_run_service.create_run(
            before_experiment_id=before_experiment_id,
            after_experiment_id=after_experiment_id,
            validation_experiment_ids=validation_experiment_ids,
            metrics_key=metrics_key,
            lender_id=lender_id,
            old_metrics_version=active_metrics.version_id,
            candidate_metrics_version=candidate_metrics_version.version_id,
            old_evaluation_config_version=active_evaluation_config.version_id,
            candidate_evaluation_config_version=candidate_evaluation_config_version.version_id,
            correctness_analysis=proposal.correctness_analysis,
            metric_actions=proposal.metric_actions,
            candidate_metrics=proposal.updated_metrics_json,
            metrics_diff_summary=proposal.metrics_diff_summary,
            candidate_evaluation_config=candidate_evaluation_config,
            evaluation_config_diff_summary=proposal.evaluation_config_diff_summary,
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
        active_evaluation_config: dict,
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
                    "You are the meta evaluator for a collections evaluation loop. "
                    "Use the global compliance rules and the company policy as the source of truth. "
                    "Treat the before and after transcripts as first-class evidence. "
                    "Determine whether the evaluator judge was correct for each experiment. "
                    "Keep changes minimal and surgical. Prefer keeping or rewriting existing metrics over adding new ones. "
                    "You may also propose a minimal update to the evaluation control config, but only within these fields: "
                    "benchmark_scenario_ids, benchmark_max_turns, required_mean_score_delta, required_win_rate, "
                    "and require_compliance_non_regression. "
                    "Add at most 3 new metrics in a single proposal, and prefer 0-2 new metrics unless a blind spot clearly requires more. "
                    "Then decide for each metric whether it should stay, be deleted, be added, or be rewritten. "
                    "Return a full candidate metrics list with policy_references for every metric, and return the full candidate evaluation config. "
                    "Return strict JSON only."
                ),
                "human_prompt": self._build_proposal_prompt(
                    before_record=before_record,
                    after_record=after_record,
                    before_transcript=before_transcript,
                    after_transcript=after_transcript,
                    active_metrics=active_metrics,
                    active_evaluation_config=active_evaluation_config,
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
        llm = build_chat_llm(
            model=self.model_name,
            temperature=0,
            model_env_keys=("OPENAI_JUDGE_MODEL", "OPENAI_MODEL", "CLAUDE_MODEL", "ANTHROPIC_MODEL"),
        )
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
        active_evaluation_config: dict,
        company_policy: str,
    ) -> str:
        return (
            f"Global compliance rules:\n{get_compliance_rules_text()}\n\n"
            f"Company policy:\n{company_policy or 'No lender policy found.'}\n\n"
            f"Active metrics version JSON:\n{json.dumps(active_metrics, indent=2)}\n\n"
            f"Active evaluation config JSON:\n{json.dumps(active_evaluation_config, indent=2)}\n\n"
            f"Before experiment record:\n{json.dumps(before_record.model_dump(), indent=2)}\n\n"
            f"Before transcript:\n{before_transcript}\n\n"
            f"After experiment record:\n{json.dumps(after_record.model_dump(), indent=2)}\n\n"
            f"After transcript:\n{after_transcript}\n\n"
            "Return JSON with:\n"
            "- correctness_analysis: one item per experiment containing judge_got_right, judge_got_wrong, judge_missed, and evidence\n"
            "- metric_actions: one item per metric decision with action keep|delete|add|rewrite, rationale, policy_references, proposed_metric when relevant, and evidence\n"
            "- updated_metrics_json: the full candidate metrics list\n"
            "- metrics_diff_summary\n"
            "- updated_evaluation_config_json: the full candidate evaluation config\n"
            "- evaluation_config_diff_summary\n"
            "- why_this_change\n"
            "- expected_improvement\n"
            "Every candidate metric in updated_metrics_json must include policy_references.\n"
            f"Do not add more than {MAX_NEW_METRICS_PER_META_EVAL} new metrics beyond the active metrics list.\n"
            "Prefer 0-2 new metrics. If an existing metric can be rewritten instead of adding a new one, rewrite it.\n"
            "Preserve existing metric_ids for kept or rewritten metrics. Use new metric_ids only for truly new metrics.\n"
            "Keep evaluation config changes minimal. If no config change is needed, return the active evaluation config unchanged."
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

        for experiment_id in self._select_curated_validation_experiment_ids(excluded_ids=excluded):
            if experiment_id in excluded or experiment_id in selected:
                continue
            selected.append(experiment_id)
            if len(selected) >= limit:
                return selected

        for record in reversed(self.judgment_record_service.list_records()):
            if record.judgment is None:
                continue
            if record.experiment_id in excluded:
                continue
            if record.experiment_id in selected:
                continue
            selected.append(record.experiment_id)
            if len(selected) >= limit:
                break

        return selected

    def _select_curated_validation_experiment_ids(self, excluded_ids: set[str]) -> list[str]:
        targets = self._load_validation_targets()
        if not targets:
            return []

        selected: list[str] = []
        runs = sorted(self.run_history_service.list_runs(), key=lambda item: item.started_at, reverse=True)

        for target in targets:
            for run in runs:
                if run.experiment_id in excluded_ids:
                    continue
                if run.experiment_id in selected:
                    continue
                if run.scenario_id != target.scenario_id:
                    continue
                if not run.evaluations:
                    continue
                selected.append(run.experiment_id)
                break

        return selected

    def _load_validation_targets(self) -> list[MetaEvalValidationTarget]:
        if not self.validation_set_path.exists():
            return []

        payload = json.loads(self.validation_set_path.read_text())
        if isinstance(payload, dict):
            payload = payload.get("targets", [])
        if not isinstance(payload, list):
            return []
        return [MetaEvalValidationTarget.model_validate(item) for item in payload]

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

        runs_by_experiment_id = {run.experiment_id: run for run in self.run_history_service.list_runs()}
        targets_by_scenario_id = {target.scenario_id: target for target in self._load_validation_targets()}
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
            run = runs_by_experiment_id.get(experiment_id)
            scenario_id = run.scenario_id if run is not None else None
            contexts.append(
                ValidationExperimentContext(
                    experiment_id=experiment_id,
                    scenario_id=scenario_id,
                    transcript=self._load_transcript(experiment_id),
                    old_judgment=old_judgment,
                    candidate_judgment=candidate_judgment,
                    target=targets_by_scenario_id.get(scenario_id or ""),
                )
            )

        return contexts

    def _evaluate_expectation_backed_validation(
        self,
        validation_contexts: list[ValidationExperimentContext],
    ) -> tuple[list[ExperimentValidationAnalysis], int, int, int]:
        results: list[ExperimentValidationAnalysis] = []
        old_expectation_matches = 0
        candidate_expectation_matches = 0
        total_expectation_checks = 0

        for context in validation_contexts:
            old_match_count, total_checks = self._score_judgment_against_target(context.old_judgment, context.target)
            candidate_match_count, _ = self._score_judgment_against_target(context.candidate_judgment, context.target)

            old_expectation_matches += old_match_count
            candidate_expectation_matches += candidate_match_count
            total_expectation_checks += total_checks

            winner = self._determine_expectation_winner(
                old_match_count=old_match_count,
                candidate_match_count=candidate_match_count,
            )
            results.append(
                ExperimentValidationAnalysis(
                    experiment_id=context.experiment_id,
                    scenario_id=context.scenario_id,
                    purpose=context.target.purpose if context.target else None,
                    expected_verdict=context.target.expected_verdict if context.target else None,
                    expected_fail_metrics=list(context.target.expected_fail_metrics) if context.target else [],
                    expected_pass_metrics=list(context.target.expected_pass_metrics) if context.target else [],
                    old_matched_checks=old_match_count,
                    candidate_matched_checks=candidate_match_count,
                    total_checks=total_checks,
                    winner=winner,
                    reason=self._build_expectation_result_reason(
                        target=context.target,
                        old_match_count=old_match_count,
                        candidate_match_count=candidate_match_count,
                        total_checks=total_checks,
                    ),
                    old_judgment=context.old_judgment,
                    candidate_judgment=context.candidate_judgment,
                )
            )

        return results, old_expectation_matches, candidate_expectation_matches, total_expectation_checks

    def _score_judgment_against_target(
        self,
        judgment: StoredJudgeResult,
        target: MetaEvalValidationTarget | None,
    ) -> tuple[int, int]:
        if target is None:
            return 0, 0

        match_count = 0
        total_checks = 0
        score_by_metric_id = {score.metric_id: score.score for score in judgment.scores}

        if target.expected_verdict:
            total_checks += 1
            if judgment.verdict.lower() == target.expected_verdict.lower():
                match_count += 1

        for metric_id in target.expected_fail_metrics:
            total_checks += 1
            metric_score = score_by_metric_id.get(metric_id)
            if metric_score is not None and metric_score <= target.fail_score_max:
                match_count += 1

        for metric_id in target.expected_pass_metrics:
            total_checks += 1
            metric_score = score_by_metric_id.get(metric_id)
            if metric_score is not None and metric_score >= target.pass_score_min:
                match_count += 1

        return match_count, total_checks

    def _determine_expectation_winner(
        self,
        old_match_count: int,
        candidate_match_count: int,
    ) -> str:
        if candidate_match_count > old_match_count:
            return "CANDIDATE"
        if old_match_count > candidate_match_count:
            return "OLD"
        return "TIE"

    def _build_expectation_result_reason(
        self,
        target: MetaEvalValidationTarget | None,
        old_match_count: int,
        candidate_match_count: int,
        total_checks: int,
    ) -> str:
        if target is None or total_checks == 0:
            return "No expectation labels were configured for this held-out experiment, so it was not used as proof-bearing validation."

        expected_parts: list[str] = []
        if target.expected_verdict:
            expected_parts.append(f"verdict={target.expected_verdict}")
        if target.expected_fail_metrics:
            expected_parts.append(f"fail metrics={', '.join(target.expected_fail_metrics)}")
        if target.expected_pass_metrics:
            expected_parts.append(f"pass metrics={', '.join(target.expected_pass_metrics)}")

        expected_text = "; ".join(expected_parts) if expected_parts else "no explicit criteria"
        return (
            f"Candidate matched {candidate_match_count}/{total_checks} labeled checks vs old {old_match_count}/{total_checks}. "
            f"Expected criteria: {expected_text}."
        )

    def _decide_expectation_backed_validation(
        self,
        old_expectation_matches: int,
        candidate_expectation_matches: int,
        total_expectation_checks: int,
        compliance_gate_reason: str | None,
    ) -> tuple[str, str]:
        if compliance_gate_reason is not None:
            return "REJECT", compliance_gate_reason

        if total_expectation_checks == 0:
            return (
                "REJECT",
                "No expectation-backed validation criteria were available on the held-out set, so the candidate metrics could not prove they were better.",
            )

        if candidate_expectation_matches > old_expectation_matches:
            return (
                "ADOPT",
                "Candidate metrics proved better on held-out labeled validation: "
                f"{candidate_expectation_matches}/{total_expectation_checks} expectation checks matched vs "
                f"{old_expectation_matches}/{total_expectation_checks} for the old metrics.",
            )

        return (
            "REJECT",
            "Candidate metrics did not prove better on held-out labeled validation: "
            f"{candidate_expectation_matches}/{total_expectation_checks} expectation checks matched vs "
            f"{old_expectation_matches}/{total_expectation_checks} for the old metrics.",
        )

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

    def _sanitize_evaluation_config_proposal(
        self,
        proposed: EvaluationConfigDraft,
        *,
        active_config: EvaluationConfig,
    ) -> EvaluationConfig:
        available_scenarios = {
            item.scenario_id
            for item in self.run_history_service.list_runs()
            if item.scenario_id
        }
        scenario_ids = [
            scenario_id
            for scenario_id in proposed.benchmark_scenario_ids
            if scenario_id in available_scenarios
        ]
        if not scenario_ids:
            scenario_ids = list(active_config.benchmark_scenario_ids)

        return EvaluationConfig(
            version_id=active_config.version_id,
            benchmark_scenario_ids=scenario_ids,
            benchmark_max_turns=max(8, min(int(proposed.benchmark_max_turns), 60)),
            required_mean_score_delta=max(0.0, min(float(proposed.required_mean_score_delta), 2.0)),
            required_win_rate=max(0.5, min(float(proposed.required_win_rate), 1.0)),
            require_compliance_non_regression=bool(proposed.require_compliance_non_regression),
            diff_summary=active_config.diff_summary,
            created_at=active_config.created_at,
        )

    def _same_evaluation_config(
        self,
        left: EvaluationConfig,
        right: EvaluationConfig,
    ) -> bool:
        return (
            left.benchmark_scenario_ids == right.benchmark_scenario_ids
            and left.benchmark_max_turns == right.benchmark_max_turns
            and left.required_mean_score_delta == right.required_mean_score_delta
            and left.required_win_rate == right.required_win_rate
            and left.require_compliance_non_regression == right.require_compliance_non_regression
        )
