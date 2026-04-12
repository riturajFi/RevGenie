from __future__ import annotations

import json

from pydantic import ValidationError

from app.domain.borrower_case import AgentTurnResult


def parse_agent_turn_result(raw_output: str) -> AgentTurnResult:
    cleaned = raw_output.strip()
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
            raise ValueError("Agent output was not valid JSON")
        payload = json.loads(cleaned[start : end + 1])
    try:
        return AgentTurnResult.model_validate(payload)
    except ValidationError as error:
        raise ValueError(f"Agent output did not match AgentTurnResult schema: {error}") from error
