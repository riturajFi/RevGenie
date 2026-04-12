from __future__ import annotations

import json
import os
from urllib import request

from experiments.llm_v0.logs import LogCollector
from experiments.llm_v0.models import TokenCountRecord
from experiments.llm_v0.store import JsonStore, utc_now


class PromptTokenCalculator:
    def __init__(self, store: JsonStore, logs: LogCollector, default_model: str = "gpt-5") -> None:
        self.store = store
        self.logs = logs
        self.default_model = default_model

    def calculate_prompt_tokens(
        self,
        input_text: str,
        model: str | None = None,
        caller_cwd: str | None = None,
    ) -> TokenCountRecord:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY must be set to calculate prompt tokens")

        payload = json.dumps(
            {
                "model": model or self.default_model,
                "input": input_text,
            }
        ).encode("utf-8")
        token_request = request.Request(
            "https://api.openai.com/v1/responses/input_tokens",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(token_request) as response:
            raw_response = json.loads(response.read().decode("utf-8"))

        input_tokens = self._extract_input_tokens(raw_response)
        record = TokenCountRecord(
            created_at=utc_now(),
            model=model or self.default_model,
            input_text=input_text,
            input_chars=len(input_text),
            input_tokens=input_tokens,
            caller_cwd=caller_cwd or os.getcwd(),
            raw_response=raw_response,
        )
        self.store.append_token_count(record)
        self.logs.collect(
            source="token_calculator",
            message="Calculated prompt tokens",
            metadata={
                "model": record.model,
                "input_chars": record.input_chars,
                "input_tokens": record.input_tokens,
            },
            caller_cwd=record.caller_cwd,
        )
        return record

    def _extract_input_tokens(self, payload: dict) -> int:
        direct = payload.get("input_tokens")
        if isinstance(direct, int):
            return direct

        usage = payload.get("usage")
        if isinstance(usage, dict):
            usage_tokens = usage.get("input_tokens")
            if isinstance(usage_tokens, int):
                return usage_tokens

        nested = self._find_nested_input_tokens(payload)
        if nested is None:
            raise ValueError(f"Could not find input token count in response: {payload}")
        return nested

    def _find_nested_input_tokens(self, value) -> int | None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key == "input_tokens" and isinstance(item, int):
                    return item
                nested = self._find_nested_input_tokens(item)
                if nested is not None:
                    return nested
        if isinstance(value, list):
            for item in value:
                nested = self._find_nested_input_tokens(item)
                if nested is not None:
                    return nested
        return None
