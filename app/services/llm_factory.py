from __future__ import annotations

import os
from typing import Any


def _env_first(*keys: str) -> str | None:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value
    return None


def _normalized_provider(model: str | None = None) -> str:
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit in {"anthropic", "claude", "openai"}:
        return "anthropic" if explicit in {"anthropic", "claude"} else "openai"
    model_name = (model or "").strip().lower()
    if model_name.startswith("claude"):
        return "anthropic"
    return "openai"


def build_chat_llm(
    *,
    model: str | None = None,
    temperature: float = 0,
    model_env_keys: tuple[str, ...] = ("OPENAI_MODEL",),
    default_openai_model: str = "gpt-4o-mini",
    default_claude_model: str = "claude-3-5-sonnet-latest",
) -> Any:
    provider = _normalized_provider(model)
    anthropic_keys = tuple(
        key for key in model_env_keys if "OPENAI" not in key.upper()
    ) + ("CLAUDE_MODEL", "ANTHROPIC_MODEL")
    openai_keys = tuple(
        key for key in model_env_keys if "CLAUDE" not in key.upper() and "ANTHROPIC" not in key.upper()
    ) + ("OPENAI_MODEL",)

    if provider == "anthropic":
        claude_api_key = os.getenv("CLAUDE_API_KEY")
        if claude_api_key and not os.getenv("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = claude_api_key
        from langchain_anthropic import ChatAnthropic

        resolved = model or _env_first(*anthropic_keys) or default_claude_model
        return ChatAnthropic(model=resolved, temperature=temperature)

    from langchain_openai import ChatOpenAI

    resolved = model or _env_first(*openai_keys) or default_openai_model
    return ChatOpenAI(model=resolved, temperature=temperature)
