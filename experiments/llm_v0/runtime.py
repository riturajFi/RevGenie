from __future__ import annotations

import json
import os
from statistics import mean
from uuid import uuid4

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from experiments.llm_v0.models import (
    AdoptionDecision,
    EvaluatorDiffResult,
    EvaluatorResult,
    ExperimentRunRecord,
    LinkedVersion,
    PromptDiffResult,
    Scenario,
    TranscriptBundle,
)
from experiments.llm_v0.store import JsonStore, build_merged_transcript, utc_now


class ExperimentRuntime:
    def __init__(
        self,
        store: JsonStore,
        model: str | None = None,
        judge_model: str | None = None,
    ) -> None:
        self.store = store
        self.model_name = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.judge_model_name = judge_model or os.getenv("OPENAI_JUDGE_MODEL", self.model_name)

    def run_single_experiment(
        self,
        loop_name: str,
        scenario: Scenario,
        prompt_version: LinkedVersion,
        evaluator_version: LinkedVersion,
    ) -> ExperimentRunRecord:
        transcript = self.generate_transcript(prompt_version.text, scenario)
        evaluation = self.evaluate_transcript(evaluator_version.text, transcript, scenario)
        record = ExperimentRunRecord(
            run_id=f"{loop_name}_{uuid4().hex[:12]}",
            loop_name=loop_name,
            scenario=scenario,
            prompt_version_id=prompt_version.version_id,
            evaluator_version_id=evaluator_version.version_id,
            transcript=transcript,
            evaluation=evaluation,
            created_at=utc_now(),
        )
        self.store.save_run(record)
        return record

    def generate_transcript(self, prompt_text: str, scenario: Scenario) -> TranscriptBundle:
        transcript = self._structured_call(
            schema=TranscriptBundle,
            model_name=self.model_name,
            system_prompt=(
                "You simulate a collector agent system. "
                "Create raw transcripts for Agent 1 chat, Agent 2 voice, and Agent 3 chat."
            ),
            human_prompt=(
                f"Current prompt:\n{prompt_text}\n\n"
                f"Original scenario:\n{scenario.original_scenario}\n\n"
                f"Task requirements:\n{json.dumps(scenario.task_requirements, indent=2)}\n\n"
                f"Compliance rules:\n{json.dumps(scenario.compliance_rules, indent=2)}\n\n"
                "Return raw transcripts. The borrower should feel one continuous conversation."
            ),
        )
        transcript.merged_transcript = build_merged_transcript(
            transcript.agent_1_chat,
            transcript.agent_2_voice,
            transcript.agent_3_chat,
        )
        return transcript

    def evaluate_transcript(
        self,
        evaluator_prompt: str,
        transcript: TranscriptBundle,
        scenario: Scenario,
    ) -> EvaluatorResult:
        return self._structured_call(
            schema=EvaluatorResult,
            model_name=self.judge_model_name,
            system_prompt=evaluator_prompt,
            human_prompt=(
                f"Full transcript:\n{transcript.merged_transcript}\n\n"
                f"Original scenario:\n{scenario.original_scenario}\n\n"
                f"Task requirements:\n{json.dumps(scenario.task_requirements, indent=2)}\n\n"
                f"Compliance rules:\n{json.dumps(scenario.compliance_rules, indent=2)}\n\n"
                f"Output format:\n{scenario.output_format}"
            ),
        )

    def propose_prompt_diff(
        self,
        current_prompt: str,
        bad_transcript: str,
        judge_feedback: EvaluatorResult,
    ) -> PromptDiffResult:
        return self._structured_call(
            schema=PromptDiffResult,
            model_name=self.judge_model_name,
            system_prompt=(
                "You improve prompts for a failing LLM system. "
                "Return a short additive prompt diff only, not a full prompt rewrite."
            ),
            human_prompt=(
                f"Current prompt:\n{current_prompt}\n\n"
                f"Bad transcript:\n{bad_transcript}\n\n"
                f"Judge feedback:\n{json.dumps(judge_feedback.model_dump(), indent=2)}"
            ),
        )

    def propose_evaluator_diff(
        self,
        current_evaluator_prompt: str,
        baseline_runs: list[ExperimentRunRecord],
    ) -> EvaluatorDiffResult:
        audit_payload = [
            {
                "scenario_id": run.scenario.scenario_id,
                "title": run.scenario.title,
                "expected_truths": run.scenario.expected_truths,
                "audit_expectations": run.scenario.audit_expectations,
                "transcript": run.transcript.merged_transcript,
                "evaluator_output": run.evaluation.model_dump(),
            }
            for run in baseline_runs
        ]
        return self._structured_call(
            schema=EvaluatorDiffResult,
            model_name=self.judge_model_name,
            system_prompt=(
                "You are the meta-evaluator. "
                "Find flaws in evaluator logic, then return a short additive evaluator diff."
            ),
            human_prompt=(
                f"Current evaluator prompt:\n{current_evaluator_prompt}\n\n"
                f"Audit package:\n{json.dumps(audit_payload, indent=2)}"
            ),
        )

    def compare_prompt_versions(
        self,
        active_prompt: LinkedVersion,
        candidate_prompt: LinkedVersion,
        baseline_runs: list[ExperimentRunRecord],
        candidate_runs: list[ExperimentRunRecord],
        baseline_summary: dict[str, float | int],
        candidate_summary: dict[str, float | int],
    ) -> AdoptionDecision:
        payload = {
            "active_prompt_version": active_prompt.version_id,
            "candidate_prompt_version": candidate_prompt.version_id,
            "baseline_summary": baseline_summary,
            "candidate_summary": candidate_summary,
            "baseline_evaluations": [run.evaluation.model_dump() for run in baseline_runs],
            "candidate_evaluations": [run.evaluation.model_dump() for run in candidate_runs],
        }
        return self._structured_call(
            schema=AdoptionDecision,
            model_name=self.judge_model_name,
            system_prompt=(
                "You decide whether a new prompt version should replace the active one. "
                "Prefer compliance first, continuity second, and resolution third. "
                "If the evidence is mixed or unclear, reject."
            ),
            human_prompt=json.dumps(payload, indent=2),
        )

    def compare_evaluator_versions(
        self,
        active_evaluator: LinkedVersion,
        candidate_evaluator: LinkedVersion,
        baseline_runs: list[ExperimentRunRecord],
        candidate_runs: list[ExperimentRunRecord],
        baseline_summary: dict[str, float | int],
        candidate_summary: dict[str, float | int],
        identified_flaws: list[str],
    ) -> AdoptionDecision:
        payload = {
            "active_evaluator_version": active_evaluator.version_id,
            "candidate_evaluator_version": candidate_evaluator.version_id,
            "identified_flaws": identified_flaws,
            "baseline_summary": baseline_summary,
            "candidate_summary": candidate_summary,
            "audit_package": [
                {
                    "scenario_id": before.scenario.scenario_id,
                    "expected_truths": before.scenario.expected_truths,
                    "audit_expectations": before.scenario.audit_expectations,
                    "old_evaluator_output": before.evaluation.model_dump(),
                    "new_evaluator_output": after.evaluation.model_dump(),
                }
                for before, after in zip(baseline_runs, candidate_runs)
            ],
        }
        return self._structured_call(
            schema=AdoptionDecision,
            model_name=self.judge_model_name,
            system_prompt=(
                "You decide whether a candidate evaluator is better than the current evaluator. "
                "Prefer the version that catches real compliance and audit expectation failures more reliably. "
                "If the candidate is not clearly better, reject."
            ),
            human_prompt=json.dumps(payload, indent=2),
        )

    def apply_diff(self, base_text: str, diff_text: str, parent_version_id: str) -> str:
        return (
            f"{base_text.strip()}\n\n"
            f"# Applied diff from {parent_version_id}\n"
            f"{diff_text.strip()}"
        )

    def pick_target_run(self, runs: list[ExperimentRunRecord]) -> ExperimentRunRecord:
        for run in runs:
            if run.evaluation.pass_fail == "FAIL":
                return run
        return min(runs, key=lambda item: item.evaluation.overall_score)

    def score_summary(self, runs: list[ExperimentRunRecord]) -> dict[str, float | int]:
        return {
            "count": len(runs),
            "pass_count": sum(1 for run in runs if run.evaluation.pass_fail == "PASS"),
            "avg_overall_score": round(mean(run.evaluation.overall_score for run in runs), 2),
            "avg_compliance_score": round(mean(run.evaluation.compliance_score for run in runs), 2),
            "avg_continuity_score": round(mean(run.evaluation.continuity_score for run in runs), 2),
            "avg_resolution_score": round(mean(run.evaluation.resolution_score for run in runs), 2),
        }

    def _structured_call(
        self,
        schema,
        model_name: str,
        system_prompt: str,
        human_prompt: str,
    ):
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{human_prompt}"),
            ]
        )
        llm = ChatOpenAI(model=model_name, temperature=0)
        chain = prompt | llm.with_structured_output(schema)
        return chain.invoke(
            {
                "system_prompt": system_prompt,
                "human_prompt": human_prompt,
            }
        )
