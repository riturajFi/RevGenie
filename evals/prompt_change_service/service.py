from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from app.services.llm_factory import build_chat_llm
from app.domain.borrower_case import CaseStatus, ResolutionMode, Stage
from app.services.borrower_case import FileBorrowerCaseService
from app.services.simulation_run_history import SimulationRunHistoryService
from evals.evaluation_config_service.service import EvaluationConfigService, evaluation_config_service
from evals.judgment_management_service.service import (
    JudgmentRecordService,
    PromptBenchmarkScenarioResult,
    PromptBenchmarkSummary,
    PromptBenchmarkThresholds,
)
from evals.judge_service.service import JudgeResult, JudgeService
from evals.logging_service import TranscriptLoggingService
from evals.logging_service.logger import LogEvent
from evals.metrics_management_service.service import MetricsRegistry
from evals.prompt_management_service.prompt_storage import (
    PromptStorageService,
    json_prompt_storage_service,
)
from evals.proposer_prompt_management_service.service import ProposerPromptManager
from evals.tester_service import (
    DEFAULT_SCENARIOS_PATH,
    ScenarioRepository,
    TesterAgent,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_LOG_DIR = REPO_ROOT / "data" / "chats" / "experiments"


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
    benchmark_result: PromptBenchmarkSummary | None = None


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
        metrics_registry: MetricsRegistry | None = None,
        evaluation_config: EvaluationConfigService | None = None,
        scenario_repository: ScenarioRepository | None = None,
        borrower_case_service: FileBorrowerCaseService | None = None,
        run_history_service: SimulationRunHistoryService | None = None,
        tester: TesterAgent | None = None,
        model: str | None = None,
    ) -> None:
        self.prompt_service = prompt_service or json_prompt_storage_service
        self.judge_service = judge_service or JudgeService()
        self.proposer_prompt_manager = proposer_prompt_manager or ProposerPromptManager()
        self.judgment_record_service = judgment_record_service or JudgmentRecordService()
        self.metrics_registry = metrics_registry or MetricsRegistry()
        self.evaluation_config = evaluation_config or evaluation_config_service
        self.scenario_repository = scenario_repository or ScenarioRepository(DEFAULT_SCENARIOS_PATH)
        self.borrower_case_service = borrower_case_service or FileBorrowerCaseService()
        self.run_history_service = run_history_service or SimulationRunHistoryService()
        self.logging_service = TranscriptLoggingService()
        self.tester = tester or TesterAgent(temperature=0)
        self.model_name = (
            model
            or os.getenv("LLM_MODEL")
            or os.getenv("OPENAI_MODEL")
            or os.getenv("CLAUDE_MODEL")
            or os.getenv("ANTHROPIC_MODEL")
        )

    def apply_change(
        self,
        experiment_id: str,
        target_agent_id: str,
        force_activate: bool = True,
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> PromptChangeApplyResult:
        self._report_progress(
            progress_callback,
            agent_id=target_agent_id,
            stage="analyzing_failure",
            message="Reading the judged conversation and finding the highest-value prompt fix.",
        )
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
        diff_summary = self._resolve_diff_summary(draft, append_prompt_lines)
        why_this_change = self._resolve_why_this_change(draft, append_prompt_lines, target_agent_id)

        if not append_prompt_lines:
            result = PromptChangeApplyResult(
                agent_id=target_agent_id,
                old_version_id=active_prompt.version_id,
                new_version_id=active_prompt.version_id,
                diff_summary=diff_summary,
                why_this_change=why_this_change,
                activation_status="no_change",
                benchmark_result=self._no_change_benchmark_summary(),
            )
            self._report_progress(
                progress_callback,
                agent_id=target_agent_id,
                stage="no_change",
                message="No new prompt change was needed because the current prompt already covered the issue.",
            )
            self.judgment_record_service.save_prompt_change(experiment_id, result)
            return result

        self._report_progress(
            progress_callback,
            agent_id=target_agent_id,
            stage="creating_candidate",
            message="Created a new prompt candidate. Starting side-by-side testing.",
        )
        new_prompt_lines = self._append_prompt_lines(active_prompt.prompt_lines, append_prompt_lines)
        new_version = self.prompt_service.create_prompt_version(
            agent_id=target_agent_id,
            prompt_text=new_prompt_lines,
            parent_version_id=active_prompt.version_id,
            diff_summary=diff_summary,
        )
        benchmark_result = self._benchmark_candidate(
            agent_id=target_agent_id,
            baseline_version_id=active_prompt.version_id,
            candidate_version_id=new_version.version_id,
            progress_callback=progress_callback,
        )

        activation_status = "rejected"
        if benchmark_result.decision == "ADOPT":
            activation_status = "candidate"
            if force_activate:
                self.prompt_service.activate_version(target_agent_id, new_version.version_id)
                activation_status = "active"
        self._report_progress(
            progress_callback,
            agent_id=target_agent_id,
            stage="finalized",
            message=benchmark_result.reason,
        )

        result = PromptChangeApplyResult(
            agent_id=target_agent_id,
            old_version_id=active_prompt.version_id,
            new_version_id=new_version.version_id,
            diff_summary=diff_summary,
            why_this_change=why_this_change,
            activation_status=activation_status,
            benchmark_result=benchmark_result,
        )
        self.judgment_record_service.save_prompt_change(experiment_id, result)
        return result

    def _propose_prompt_change(
        self,
        target_agent_id: str,
        current_prompt: str,
        current_prompt_lines: list[str],
        judge_result: JudgeResult,
        transcript: str,
    ) -> PromptChangeDraft:
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{human_prompt}"),
            ]
        )
        llm = build_chat_llm(
            model=self.model_name,
            temperature=0,
            model_env_keys=("OPENAI_MODEL", "CLAUDE_MODEL", "ANTHROPIC_MODEL"),
        )
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

    def _benchmark_candidate(
        self,
        *,
        agent_id: str,
        baseline_version_id: str,
        candidate_version_id: str,
        metrics_key: str = "collections_agent_eval",
        progress_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> PromptBenchmarkSummary:
        config = self.evaluation_config.get_active()
        metrics_version = self.metrics_registry.get_active_metrics(metrics_key)
        compliance_metric_ids = self._compliance_metric_ids(metrics_version.metrics)
        scenario_results: list[PromptBenchmarkScenarioResult] = []
        total_runs = len(config.benchmark_scenario_ids) * 2
        completed_runs = 0

        for scenario_id in config.benchmark_scenario_ids:
            scenario = self.scenario_repository.get(scenario_id)
            borrower_id = scenario.borrower_id or ""
            if not borrower_id:
                raise ValueError(f"Scenario {scenario_id} is missing borrower_id for benchmark execution")

            self._report_progress(
                progress_callback,
                agent_id=agent_id,
                stage="testing_baseline",
                message=f"Testing current prompt on scenario {scenario_id}.",
                completed_runs=completed_runs,
                total_runs=total_runs,
                scenario_id=scenario_id,
                variant="current_prompt",
                reset_transcript=True,
            )
            baseline_judgment, lender_id = self._run_benchmark_trial(
                borrower_id=borrower_id,
                scenario_id=scenario_id,
                target_agent_id=agent_id,
                prompt_version_id=baseline_version_id,
                max_turns=config.benchmark_max_turns,
                metrics_key=metrics_key,
                event_callback=lambda event, scenario_id=scenario_id: self._report_progress(
                    progress_callback,
                    agent_id=agent_id,
                    stage="testing_baseline",
                    scenario_id=scenario_id,
                    variant="current_prompt",
                    transcript_event=event,
                ),
            )
            completed_runs += 1
            self._report_progress(
                progress_callback,
                agent_id=agent_id,
                stage="testing_candidate",
                message=f"Testing new prompt on scenario {scenario_id}.",
                completed_runs=completed_runs,
                total_runs=total_runs,
                scenario_id=scenario_id,
                variant="new_prompt",
                reset_transcript=True,
            )
            candidate_judgment, _ = self._run_benchmark_trial(
                borrower_id=borrower_id,
                scenario_id=scenario_id,
                target_agent_id=agent_id,
                prompt_version_id=candidate_version_id,
                max_turns=config.benchmark_max_turns,
                metrics_key=metrics_key,
                event_callback=lambda event, scenario_id=scenario_id: self._report_progress(
                    progress_callback,
                    agent_id=agent_id,
                    stage="testing_candidate",
                    scenario_id=scenario_id,
                    variant="new_prompt",
                    transcript_event=event,
                ),
            )
            completed_runs += 1

            baseline_compliance = self._mean_metric_score(baseline_judgment, compliance_metric_ids)
            candidate_compliance = self._mean_metric_score(candidate_judgment, compliance_metric_ids)
            winner = self._winner(baseline_judgment.overall_score, candidate_judgment.overall_score)
            scenario_results.append(
                PromptBenchmarkScenarioResult(
                    scenario_id=scenario_id,
                    borrower_id=borrower_id,
                    lender_id=lender_id,
                    baseline_experiment_id=baseline_judgment.experiment_id,
                    candidate_experiment_id=candidate_judgment.experiment_id,
                    baseline_score=baseline_judgment.overall_score,
                    candidate_score=candidate_judgment.overall_score,
                    baseline_verdict=baseline_judgment.verdict,
                    candidate_verdict=candidate_judgment.verdict,
                    baseline_compliance_score=round(baseline_compliance, 4),
                    candidate_compliance_score=round(candidate_compliance, 4),
                    compliance_delta=round(candidate_compliance - baseline_compliance, 4),
                    winner=winner,
                )
            )
            self._report_progress(
                progress_callback,
                agent_id=agent_id,
                stage="judged_scenario",
                message=f"Finished scoring scenario {scenario_id}. Winner: {winner}.",
                completed_runs=completed_runs,
                total_runs=total_runs,
                scenario_id=scenario_id,
            )

        total = max(len(scenario_results), 1)
        baseline_mean_score = sum(item.baseline_score for item in scenario_results) / total
        candidate_mean_score = sum(item.candidate_score for item in scenario_results) / total
        baseline_pass_rate = sum(item.baseline_verdict == "pass" for item in scenario_results) / total
        candidate_pass_rate = sum(item.candidate_verdict == "pass" for item in scenario_results) / total
        candidate_win_rate = sum(item.winner == "candidate" for item in scenario_results) / total
        baseline_mean_compliance = self._mean_values([item.baseline_compliance_score for item in scenario_results])
        candidate_mean_compliance = self._mean_values([item.candidate_compliance_score for item in scenario_results])
        mean_score_delta = candidate_mean_score - baseline_mean_score
        compliance_non_regression = candidate_mean_compliance >= baseline_mean_compliance - 1e-9
        thresholds = PromptBenchmarkThresholds(
            required_mean_score_delta=config.required_mean_score_delta,
            required_win_rate=config.required_win_rate,
            require_compliance_non_regression=config.require_compliance_non_regression,
        )
        decision, reason = self._benchmark_decision(
            mean_score_delta=mean_score_delta,
            candidate_win_rate=candidate_win_rate,
            compliance_non_regression=compliance_non_regression,
            thresholds=thresholds,
        )
        return PromptBenchmarkSummary(
            decision=decision,
            reason=reason,
            scenario_ids=[item.scenario_id for item in scenario_results],
            thresholds=thresholds,
            baseline_mean_score=round(baseline_mean_score, 4),
            candidate_mean_score=round(candidate_mean_score, 4),
            mean_score_delta=round(mean_score_delta, 4),
            baseline_pass_rate=round(baseline_pass_rate, 4),
            candidate_pass_rate=round(candidate_pass_rate, 4),
            candidate_win_rate=round(candidate_win_rate, 4),
            baseline_mean_compliance_score=round(baseline_mean_compliance, 4),
            candidate_mean_compliance_score=round(candidate_mean_compliance, 4),
            compliance_non_regression=compliance_non_regression,
            scenario_results=scenario_results,
        )

    def _run_benchmark_trial(
        self,
        *,
        borrower_id: str,
        scenario_id: str,
        target_agent_id: str,
        prompt_version_id: str,
        max_turns: int,
        metrics_key: str,
        event_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[JudgeResult, str]:
        workflow_id = self._generate_id("bench_wf")
        experiment_id = self._generate_id("bench_exp")
        self._reset_case_for_trial(borrower_id, workflow_id)
        borrower_case = self.borrower_case_service.get_borrower_case(borrower_id)
        if borrower_case is None:
            raise ValueError(f"Borrower case not found for {borrower_id}")
        lender_id = borrower_case.lender_id
        self._clear_experiment_log(experiment_id)
        self.tester.run(
            borrower_id=borrower_id,
            workflow_id=workflow_id,
            max_turns=max_turns,
            experiment_id=experiment_id,
            project_context_id="collections_v1",
            scenario_id=scenario_id,
            prompt_version_overrides={target_agent_id: prompt_version_id},
            event_callback=event_callback,
        )
        result = self.judge_service.judge_experiment(
            workflow_id=workflow_id,
            metrics_key=metrics_key,
            lender_id=lender_id,
            persist=False,
        )
        return result, lender_id

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
        events = self.logging_service.get_logs(experiment_id)
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

    def _compliance_metric_ids(self, metrics) -> list[str]:
        ids = [
            metric.metric_id
            for metric in metrics
            if any("Compliance Rule" in reference for reference in metric.policy_references)
        ]
        return ids or [metric.metric_id for metric in metrics]

    def _mean_metric_score(self, result: JudgeResult, metric_ids: list[str]) -> float:
        scores = [item.score for item in result.scores if item.metric_id in metric_ids]
        if not scores:
            return result.overall_score
        return sum(scores) / len(scores)

    def _winner(self, baseline_score: float, candidate_score: float) -> str:
        if candidate_score > baseline_score:
            return "candidate"
        if candidate_score < baseline_score:
            return "baseline"
        return "tie"

    def _benchmark_decision(
        self,
        *,
        mean_score_delta: float,
        candidate_win_rate: float,
        compliance_non_regression: bool,
        thresholds: PromptBenchmarkThresholds,
    ) -> tuple[str, str]:
        if thresholds.require_compliance_non_regression and not compliance_non_regression:
            return "REJECT", "Candidate prompt regressed on compliance-linked metrics."
        if mean_score_delta < thresholds.required_mean_score_delta:
            return (
                "REJECT",
                f"Candidate improved mean score by {mean_score_delta:.2f}, below the required delta of {thresholds.required_mean_score_delta:.2f}.",
            )
        if candidate_win_rate < thresholds.required_win_rate:
            return (
                "REJECT",
                f"Candidate won {candidate_win_rate:.2%} of benchmark scenarios, below the required win rate of {thresholds.required_win_rate:.2%}.",
            )
        return "ADOPT", "Candidate cleared the benchmark gate on score lift, scenario wins, and compliance stability."

    def _reset_case_for_trial(self, borrower_id: str, workflow_id: str) -> None:
        borrower_case = self.borrower_case_service.get_borrower_case(borrower_id)
        if borrower_case is None:
            raise KeyError(f"Borrower case not found for {borrower_id}")

        borrower_case.workflow_id = workflow_id
        borrower_case.stage = Stage.ASSESSMENT
        borrower_case.case_status = CaseStatus.OPEN
        borrower_case.final_disposition = None
        borrower_case.latest_handoff_summary = None
        borrower_case.attributes = {}
        borrower_case.resolution_mode = ResolutionMode.CHAT
        borrower_case.resolution_call_id = None
        borrower_case.resolution_call_status = None
        borrower_case.prompt_version_overrides = {}
        self.borrower_case_service.update_borrower_case(borrower_id, borrower_case)

    def _clear_experiment_log(self, experiment_id: str) -> None:
        for suffix in (".jsonl", ".json"):
            path = EXPERIMENT_LOG_DIR / f"{experiment_id}{suffix}"
            if path.exists():
                path.unlink()

    def _generate_id(self, prefix: str) -> str:
        now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{prefix}_{now}_{uuid4().hex[:6]}"

    def _no_change_benchmark_summary(self) -> PromptBenchmarkSummary:
        config = self.evaluation_config.get_active()
        return PromptBenchmarkSummary(
            decision="NO_CHANGE",
            reason="The prompt already covered the observed failure, so no candidate version was benchmarked.",
            scenario_ids=config.benchmark_scenario_ids,
            thresholds=PromptBenchmarkThresholds(
                required_mean_score_delta=config.required_mean_score_delta,
                required_win_rate=config.required_win_rate,
                require_compliance_non_regression=config.require_compliance_non_regression,
            ),
            baseline_mean_score=0,
            candidate_mean_score=0,
            mean_score_delta=0,
            baseline_pass_rate=0,
            candidate_pass_rate=0,
            candidate_win_rate=0,
            baseline_mean_compliance_score=0,
            candidate_mean_compliance_score=0,
            compliance_non_regression=True,
            scenario_results=[],
        )

    def _mean_values(self, values: list[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _report_progress(
        self,
        callback: Callable[[dict[str, Any]], None] | None,
        **payload: Any,
    ) -> None:
        if callback is None:
            return
        callback(payload)
