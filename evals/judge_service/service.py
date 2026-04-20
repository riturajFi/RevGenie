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
    verdict: str | None = None


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
                    You are a strict transcript judge.

                    Return JSON only.
                    Return one complete object.
                    Never return a partial object.
                    Never omit required keys.

                    Required top-level keys:
                    - experiment_id
                    - scores
                    - overall_score
                    - verdict

                    scores rules:
                    - scores must be an object
                    - keys must be the active metric ids
                    - include every active metric id exactly once
                    - do not add extra metric ids

                    Each scores entry must contain:
                    - metric_id
                    - name
                    - score
                    - reason

                    score rules:
                    - score must be a number from 0 to 10
                    - overall_score must be a number from 0 to 10
                    - verdict must be exactly "pass" or "fail"

                    If you cannot justify a high score from the transcript, score lower.
                    If there is a serious compliance or policy breach, default to fail.
                    Base every reason on the transcript, compliance rules, and company policy.

                    Active metric ids:
                    {metric_ids}

                    Active metrics JSON:
                    {metrics_json}
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
            result = structured_llm.invoke(messages)
            verdict = str(result.verdict or "").lower().strip()
            if verdict not in {"pass", "fail"}:
                verdict = "pass" if result.overall_score >= 7 else "fail"
            result.verdict = verdict
            print("Judge output:")
            print(json.dumps(result.model_dump(), indent=2))
            return result
        except Exception as exc:
            error_type = type(exc).__name__
            error_message = str(exc).strip() or "no error message"
            raise RuntimeError(
                f"Judge evaluation failed for experiment {experiment_id}: {error_type}: {error_message}"
            ) from exc

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
            "Task:\n"
            "Return one complete JSON object.\n"
            "Do not return a partial object.\n"
            "Do not omit scores.\n"
            "Do not omit overall_score.\n"
            "Do not omit verdict.\n"
            "Use experiment_id exactly as provided.\n"
            f"Use scores for exactly these metric ids: {', '.join(metric_ids) if metrics else 'none'}.\n"
            "scores must be an object keyed by metric_id.\n"
            "Each score entry must include metric_id, name, score, reason.\n"
            'verdict must be exactly "pass" or "fail".\n'
            "Ground every score in the transcript, compliance rules, and company policy."
        )
