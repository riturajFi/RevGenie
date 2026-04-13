from __future__ import annotations

import json
import os
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from experiment_harness.logging_service.logger import get_logs, get_logs_by_workflow
from metrics_management_service.service import MetricDefinition, MetricsRegistry


THIS_DIR = Path(__file__).resolve().parent
DEFAULT_JUDGMENTS_DIR = THIS_DIR.parent / "data" / "judgments"


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
        model: str | None = None,
    ) -> None:
        self.metric_registry = metric_registry or MetricsRegistry()
        self.judgment_store = judgment_store or JudgmentStore()
        self.model_name = model or os.getenv("OPENAI_JUDGE_MODEL", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    def judge_experiment(
        self,
        experiment_id: str | None = None,
        metrics_key: str = "collections_agent_eval",
        workflow_id: str | None = None,
    ) -> JudgeResult:
        transcript, result_experiment_id = self._load_transcript(
            experiment_id=experiment_id,
            workflow_id=workflow_id,
        )
        metrics = self.metric_registry.get_active_metrics(metrics_key).metrics
        result = self._call_judge_llm(
            experiment_id=result_experiment_id,
            transcript=transcript,
            metrics=metrics,
        )
        self.judgment_store.save(result)
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
                    "Read the transcript and metrics, then return strict JSON only."
                ),
                "human_prompt": self._build_human_prompt(experiment_id, transcript, metrics),
            }
        )

    def _build_human_prompt(
        self,
        experiment_id: str,
        transcript: str,
        metrics: list[MetricDefinition],
    ) -> str:
        metrics_json = json.dumps([metric.model_dump() for metric in metrics], indent=2)
        return (
            f"Experiment ID:\n{experiment_id}\n\n"
            f"Active metrics JSON:\n{metrics_json}\n\n"
            f"Full transcript:\n{transcript}\n\n"
            "Return JSON with:\n"
            "- experiment_id\n"
            "- scores: one item per metric with metric_id, name, score, reason\n"
            "- overall_score\n"
            '- verdict: "pass" or "fail"\n'
            "Use the metrics exactly as provided."
        )
