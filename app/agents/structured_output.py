from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.domain.borrower_case import AgentStageOutcome, AgentTurnResult


def _as_text(raw_output: Any) -> str:
    if isinstance(raw_output, str):
        return raw_output
    if isinstance(raw_output, list):
        parts: list[str] = []
        for item in raw_output:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
                    continue
                # Anthropic-style content blocks may nest text under type-specific fields.
                for key in ("content", "value"):
                    nested = item.get(key)
                    if isinstance(nested, str):
                        parts.append(nested)
                        break
        return "\n".join(part for part in parts if part).strip()
    if isinstance(raw_output, dict):
        for key in ("output", "text", "content"):
            value = raw_output.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, list):
                return _as_text(value)
    return str(raw_output)


def parse_agent_turn_result(raw_output: Any) -> AgentTurnResult:
    cleaned = _as_text(raw_output).strip()
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
        if isinstance(payload, dict):
            reply_value = payload.get("reply")
            if reply_value is None:
                payload = dict(payload)
                payload["reply"] = ""
                return AgentTurnResult.model_validate(payload)
            if isinstance(reply_value, str):
                return AgentTurnResult(
                    reply=reply_value,
                    stage_outcome=AgentStageOutcome.CONTINUE,
                    case_delta={},
                    latest_handoff_summary=None,
                )
        if isinstance(payload, dict) and isinstance(payload.get("reply"), str):
            return AgentTurnResult(
                reply=payload["reply"],
                stage_outcome=AgentStageOutcome.CONTINUE,
                case_delta={},
                latest_handoff_summary=None,
            )
        raise ValueError(f"Agent output did not match AgentTurnResult schema: {error}") from error
