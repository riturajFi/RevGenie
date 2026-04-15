from __future__ import annotations

import json
import os
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from evals.logging_service.logger import get_logs, get_logs_by_workflow
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
    scores: list[JudgeScore]
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
        self.model_name = model or os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

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
            events = get_logs_by_workflow(workflow_id)
            if not events:
                raise ValueError(f"No transcript logs found for workflow_id: {workflow_id}")
            resolved_experiment_id = events[0].experiment_id or workflow_id
        elif experiment_id:
            events = get_logs(experiment_id)
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
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                ("human", "{human_prompt}"),
            ]
        )
        llm = ChatOpenAI(model=self.model_name, temperature=0)
        chain = prompt | llm.with_structured_output(JudgeResult)
        return chain.invoke(
            {
                "system_prompt": (
                    "You are a strict collections experiment judge. "
                    "Evaluate the transcript at the full system level, not just turn by turn. "
                    "Judge the interaction against the compliance rules, the lender company policy, the active metrics, stage correctness, and cross-agent continuity. "
                    "Use the explicit agent role definitions as binding evaluation context. "
                    "Penalize any agent that takes up another agent's role or skips its own role. "
                    "You must explicitly judge whether Agent 1 actually performed assessment first by establishing the debt, verifying identity appropriately, and gathering the borrower's financial situation, or whether it skipped assessment and jumped early into negotiation, offer-making, threats, or closure language. "
                    "Agent 1 is not the negotiator and should not be judged as if it must complete Agent 2's role unless the compliance or company policy explicitly requires a step at that stage. "
                    "You must explicitly judge whether Agent 2 proposed settlement options that are aligned with lender policy, and whether all offers, discounts, payment plans, hardship referrals, deadlines, and commitments stayed within allowed company policy ranges and rules. "
                    "Agent 2 is the primary resolution-stage dealmaker and hardship-routing stage. "
                    "Agent 3 is the final notice stage and should be judged as the closer, not as the primary assessor or negotiator. "
                    "You must flag any invented, unauthorized, misleading, or out-of-policy offer. "
                    "You must explicitly judge whether the AI feels like one continuous system across stages, or whether it repeats the same questions, re-verifies unnecessarily, restates already known facts, re-introduces itself awkwardly, or otherwise reveals the handoff seam. "
                    "Penalize repeated questioning, repeated explanations, and broken conversational continuity. "
                    "Be strict. Do not give credit for partial alignment when the transcript shows clear failures. "
                    "Prefer false negatives over false positives. "
                    "Return strict JSON only."
                ),
                "human_prompt": self._build_human_prompt(
                    experiment_id,
                    transcript,
                    metrics,
                    company_policy,
                ),
            }
        )

    def _build_human_prompt(
        self,
        experiment_id: str,
        transcript: str,
        metrics: list[MetricDefinition],
        company_policy: str,
    ) -> str:
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
            "- scores: one item per metric with metric_id, name, score, reason\n"
            "- overall_score\n"
            '- verdict: "pass" or "fail"\n'
            "Use the metrics exactly as provided and ground your reasoning in the compliance rules and company policy."
        )
