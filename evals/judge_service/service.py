from __future__ import annotations

import json
import os
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.services.llm_factory import build_chat_llm
from evals.logging_service import TranscriptLoggingService
from evals.judgment_management_service.service import JudgmentRecordService
from evals.metrics_management_service.service import MetricDefinition, MetricsRegistry
from evals.policy_context import AGENT_ROLE_GUIDANCE_TEXT, get_company_policy_text, get_compliance_rules_text


THIS_DIR = Path(__file__).resolve().parent
DEFAULT_JUDGMENTS_DIR = THIS_DIR.parents[1] / "data" / "evals" / "judgments"


class JudgeScore(BaseModel):
    metric_id: str
    name: str
    score: float = Field(ge=0, le=10)
    reason: str


class JudgeResult(BaseModel):
    experiment_id: str
    scores: dict[str, JudgeScore]
    overall_score: float = Field(ge=0, le=10)
    verdict: str


class JudgmentStore:
    def __init__(self, judgments_dir: Path = DEFAULT_JUDGMENTS_DIR) -> None:
        self.judgments_dir = judgments_dir
        self.judgments_dir.mkdir(parents=True, exist_ok=True)

    def save(self, result: JudgeResult) -> Path:
        path = self.judgments_dir / f"{result.experiment_id}.json"
        path.write_text(json.dumps(result.model_dump(), indent=2))
        return path

    def get(self, experiment_id: str) -> JudgeResult:
        path = self.judgments_dir / f"{experiment_id}.json"
        return JudgeResult.model_validate(json.loads(path.read_text()))


class JudgeService:
    def __init__(
        self,
        metric_registry: MetricsRegistry | None = None,
        judgment_store: JudgmentStore | None = None,
        judgment_record_service: JudgmentRecordService | None = None,
        model: str | None = None,
    ) -> None:
        self.metric_registry = metric_registry or MetricsRegistry()
        self.judgment_store = judgment_store or JudgmentStore()
        self.judgment_record_service = judgment_record_service or JudgmentRecordService()
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

    def judge_experiment(
        self,
        experiment_id: str | None = None,
        metrics_key: str = "collections_agent_eval",
        workflow_id: str | None = None,
        lender_id: str | None = None,
        metrics_version_id: str | None = None,
        persist: bool = True,
    ) -> JudgeResult:
        transcript, result_experiment_id = self._load_transcript(
            experiment_id=experiment_id,
            workflow_id=workflow_id,
        )
        metrics_version = (
            self.metric_registry.get_metrics_version(metrics_key, metrics_version_id)
            if metrics_version_id
            else self.metric_registry.get_active_metrics(metrics_key)
        )
        company_policy = get_company_policy_text(lender_id)
        result = self._call_judge_llm(
            experiment_id=result_experiment_id,
            transcript=transcript,
            metrics=metrics_version.metrics,
            company_policy=company_policy,
        )
        if persist:
            self.judgment_store.save(result)
            self.judgment_record_service.save_judgment_result(result)
        return result

    def get_judgment(self, experiment_id: str) -> JudgeResult:
        return self.judgment_store.get(experiment_id)

    def _load_transcript(
        self,
        experiment_id: str | None = None,
        workflow_id: str | None = None,
    ) -> tuple[str, str]:
        if workflow_id:
            events = self.logging_service.get_logs_by_workflow(workflow_id)
            if not events:
                raise ValueError(f"No transcript logs found for workflow_id: {workflow_id}")
            resolved_experiment_id = events[0].experiment_id or workflow_id
        elif experiment_id:
            events = self.logging_service.get_logs(experiment_id)
            if not events:
                raise ValueError(f"No transcript logs found for experiment_id: {experiment_id}")
            resolved_experiment_id = experiment_id
        else:
            raise ValueError("Either experiment_id or workflow_id is required")
        lines = []
        for event in events:
            actor = event.actor or "unknown"
            lines.append(f"[{event.created_at}] {actor}: {event.message_text}")
        return "\n".join(lines), resolved_experiment_id

    def _call_judge_llm(
        self,
        experiment_id: str,
        transcript: str,
        metrics: list[MetricDefinition],
        company_policy: str,
    ) -> JudgeResult:
        metric_ids = [metric.metric_id for metric in metrics]
        metrics_json = json.dumps([metric.model_dump() for metric in metrics], indent=2)
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
        payload = {
            "system_prompt": (
                f"""
                    You are a strict LLM chat judge for a multi-agent debt collections system.

                    You must judge the transcript very strictly, quantitatively, and at the full system level.
                    Do not judge isolated turns only.
                    Judge the end-to-end interaction.

                    Your evaluation axes are:

                    1. agentwise_duty
                    - Did each agent stay inside its assigned role?
                    - Did Agent 1 do assessment only?
                    - Did Agent 1 establish the debt, verify identity appropriately, and gather the borrower’s financial situation before handoff?
                    - Did Agent 1 avoid negotiation, offer-making, deadline discussion, payoff discussion, and closure language?
                    - Did Agent 2 handle resolution only?
                    - Did Agent 2 avoid redoing assessment unless clearly required?
                    - Did Agent 2 make policy-valid proposals only?
                    - Did Agent 3 behave like a final notice / closer stage only?
                    - Did any agent take over another agent’s job?

                    2. compliance
                    - Did the agents follow required disclosures?
                    - Did they avoid prohibited disclosures?
                    - Did they avoid revealing unnecessary personal data?
                    - Did they avoid invented facts, invented policy, invented consequences, or misleading claims?
                    - Did they comply with recording / AI disclosure requirements where applicable?
                    - Did they avoid threatening, coercive, abusive, or non-compliant language?
                    - Did they avoid unauthorized commitments?

                    3. company_policy
                    - Did all settlement options, discounts, waivers, deadlines, payment plans, hardship routes, and commitments remain inside lender policy?
                    - Did any agent reveal or apply policy that was out of scope for its role?
                    - Did any agent make invented, unauthorized, misleading, or out-of-policy offers?
                    - Did any agent compute or communicate payoff figures, discount amounts, installment schedules, or closure terms without role authority?
                    - Did the system respect policy boundaries across stages?

                    4. stage_correctness
                    - Did the conversation move through the correct stage logic?
                    - Did Agent 1 actually complete assessment before handoff?
                    - Did the system avoid premature handoff, premature closure, or premature negotiation?
                    - Did Agent 2 enter only when the case was ready for resolution?
                    - Did Agent 3 act only when final notice behavior was appropriate?

                    5. continuity
                    - Did the AI feel like one continuous system across stages?
                    - Did later agents reuse already known information correctly?
                    - Did the system avoid repeated questioning, repeated verification, repeated introductions, or awkward restarts?
                    - Did the system expose the internal handoff seam?
                    - Did it preserve conversational continuity and state continuity?

                    Scoring instructions:

                    - Be strict.
                    - Prefer false negatives over false positives.
                    - Do not give credit for partial alignment when the transcript shows clear failure.
                    - Small violations should reduce score.
                    - Major violations should reduce score sharply.
                    - Unauthorized offer-making, stage leakage, invented policy, compliance failures, and broken continuity are high-severity failures.
                    - If one agent clearly violates its role, reflect that explicitly in both reasoning and score.

                    Required evaluation behavior:

                    - Explicitly judge whether Agent 1 performed real assessment first.
                    - Explicitly judge whether Agent 1 leaked into negotiation or offer-making.
                    - Explicitly judge whether Agent 2’s terms stayed within policy.
                    - Explicitly judge whether any agent exposed policy content that belonged to a later stage.
                    - Explicitly judge whether the borrower experience felt like one continuous company conversation.
                    - Explicitly judge whether cross-agent memory and handoff quality were correct.

                    Output requirements:

                    Return strict JSON only.

                    Active metrics JSON:
                    {metrics_json}

                    Additional rules:

                    - Be concise but specific.
                    - Do not output markdown.
                    - Do not output prose outside JSON.
                    - If an agent is absent from the transcript, score only based on available evidence and say so in notes.
                    - If there is a critical compliance or policy breach, FAIL should be the default.
                    - Score exactly the active metric ids provided in the human prompt.
                    - Active metric ids are: {metric_ids}
                    """
            ),
            "human_prompt": self._build_human_prompt(
                experiment_id,
                transcript,
                metrics,
                company_policy,
            ),
        }
        try:
            messages = prompt.format_messages(**payload)
            structured_llm = llm.with_structured_output(JudgeResult)
            return structured_llm.invoke(messages)
        except Exception:
            raise RuntimeError(f"Judge evaluation failed for experiment {experiment_id}")

    def _build_human_prompt(
        self,
        experiment_id: str,
        transcript: str,
        metrics: list[MetricDefinition],
        company_policy: str,
    ) -> str:
        metric_ids = [metric.metric_id for metric in metrics]
        metrics_json = json.dumps([metric.model_dump() for metric in metrics], indent=2)
        return (
            f"Experiment ID:\n{experiment_id}\n\n"
            f"Agent role guidance:\n{AGENT_ROLE_GUIDANCE_TEXT}\n\n"
            f"Global compliance rules:\n{get_compliance_rules_text()}\n\n"
            f"Company policy:\n{company_policy or 'No lender policy found.'}\n\n"
            f"Active metrics JSON:\n{metrics_json}\n\n"
            f"Full transcript:\n{transcript}\n\n"
            "Return JSON with:\n"
            "- experiment_id\n"
            "- scores: object keyed by metric_id, one entry per active metric, each with metric_id, name, score, reason\n"
            "- overall_score\n"
            '- verdict: "pass" or "fail"\n'
            f"- score exactly these metric ids: {', '.join(metric_ids) if metrics else 'none'}\n"
            "Use the metrics exactly as provided and ground your reasoning in the compliance rules and company policy."
        )
