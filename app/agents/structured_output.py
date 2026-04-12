from __future__ import annotations

import json

from pydantic import ValidationError

from app.domain.borrower_case import AgentStageOutcome, AgentTurnResult


def parse_agent_turn_result(raw_output: str) -> AgentTurnResult:
    cleaned = raw_output.strip()
    if not cleaned:
        return AgentTurnResult(
            reply="",
            stage_outcome=AgentStageOutcome.CONTINUE,
            case_delta={},
            latest_handoff_summary=None,
        )
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            cleaned = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return AgentTurnResult(
                reply=cleaned,
                stage_outcome=AgentStageOutcome.CONTINUE,
                case_delta={},
                latest_handoff_summary=None,
            )
        try:
            payload = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            return AgentTurnResult(
                reply=cleaned,
                stage_outcome=AgentStageOutcome.CONTINUE,
                case_delta={},
                latest_handoff_summary=None,
            )
    try:
        return AgentTurnResult.model_validate(payload)
    except ValidationError as error:
        if isinstance(payload, dict) and isinstance(payload.get("reply"), str):
            return AgentTurnResult(
                reply=payload["reply"],
                stage_outcome=AgentStageOutcome.CONTINUE,
                case_delta={},
                latest_handoff_summary=None,
            )
        raise ValueError(f"Agent output did not match AgentTurnResult schema: {error}") from error
