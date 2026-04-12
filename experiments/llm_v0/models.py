from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Scenario(BaseModel):
    scenario_id: str
    title: str
    original_scenario: str
    task_requirements: list[str] = Field(default_factory=list)
    compliance_rules: list[str] = Field(default_factory=list)
    output_format: str = "Return structured JSON."
    expected_truths: list[str] = Field(default_factory=list)
    audit_expectations: list[str] = Field(default_factory=list)


class TranscriptBundle(BaseModel):
    agent_1_chat: str
    agent_2_voice: str
    agent_3_chat: str
    merged_transcript: str = ""


class LinkedVersion(BaseModel):
    version_id: str
    kind: Literal["prompt", "evaluator"]
    text: str
    diff: str | None = None
    previous_version_id: str | None = None
    next_version_id: str | None = None
    created_at: str


class ExperimentState(BaseModel):
    active_prompt_version: str = "prompt_v1"
    active_evaluator_version: str = "evaluator_v1"
    next_prompt_number: int = 2
    next_evaluator_number: int = 2
    next_log_sequence: int = 1


class EvaluatorResult(BaseModel):
    overall_score: float = Field(ge=0, le=10)
    compliance_score: float = Field(ge=0, le=10)
    continuity_score: float = Field(ge=0, le=10)
    resolution_score: float = Field(ge=0, le=10)
    failure_reasons: list[str] = Field(default_factory=list)
    suggested_prompt_changes: list[str] = Field(default_factory=list)
    pass_fail: Literal["PASS", "FAIL"]


class PromptDiffResult(BaseModel):
    prompt_diff: str


class EvaluatorDiffResult(BaseModel):
    evaluator_diff: str
    identified_flaws: list[str] = Field(default_factory=list)


class AdoptionDecision(BaseModel):
    decision: Literal["ADOPT", "REJECT"]
    reason: str


class ExperimentRunRecord(BaseModel):
    run_id: str
    loop_name: str
    scenario: Scenario
    prompt_version_id: str
    evaluator_version_id: str
    transcript: TranscriptBundle
    evaluation: EvaluatorResult
    created_at: str


class LoopSummary(BaseModel):
    baseline_summary: dict[str, float | int]
    candidate_summary: dict[str, float | int]
    decision: AdoptionDecision
    candidate_version_id: str
    active_prompt_version: str | None = None
    active_evaluator_version: str | None = None


class LogEntry(BaseModel):
    sequence: int
    created_at: str
    source: str
    caller_cwd: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class VersionAuditEvent(BaseModel):
    event_type: Literal["INIT", "CREATE_CANDIDATE", "ADOPT", "REJECT", "REVERT"]
    version_kind: Literal["prompt", "evaluator"]
    version_id: str
    created_at: str
    details: dict[str, Any] = Field(default_factory=dict)
