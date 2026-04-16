from __future__ import annotations

import json
import os
from importlib import import_module
from typing import Any
from urllib import request
from urllib.error import HTTPError, URLError

from app.domain.borrower_case import BorrowerCase
from app.domain.borrower_profile import BorrowerProfile


class RetellConfigurationError(RuntimeError):
    pass


class RetellAPIError(RuntimeError):
    pass


class RetellWebhookVerificationError(RuntimeError):
    pass


class RetellService:
    def _config(self) -> dict[str, Any]:
        return {
            "base_url": os.getenv("RETELL_BASE_URL", "https://api.retellai.com").rstrip("/"),
            "api_key": os.getenv("RETELL_API_KEY", "").strip(),
            "agent_id": os.getenv("RETELL_AGENT_ID", "").strip(),
            "from_number": os.getenv("RETELL_FROM_NUMBER", "").strip(),
            "webhook_verification_enabled": (
                os.getenv("RETELL_VALIDATE_SIGNATURES", "false").strip().lower() in {"1", "true", "yes", "on"}
            ),
        }

    def place_phone_call(
        self,
        borrower_case: BorrowerCase,
        borrower_profile: BorrowerProfile,
        handoff_summary: str | None,
    ) -> dict[str, Any]:
        config = self._config()
        self._assert_outbound_call_configured(config)
        from_number = self._normalize_phone_number(config["from_number"], label="RETELL_FROM_NUMBER")
        to_number = self._normalize_phone_number(borrower_profile.phone_number, label="borrower phone number")
        payload = {
            "from_number": from_number,
            "to_number": to_number,
            "override_agent_id": config["agent_id"],
            "metadata": {
                "borrower_id": borrower_case.borrower_id,
                "workflow_id": borrower_case.workflow_id,
                "lender_id": borrower_case.lender_id,
                "resolution_mode": borrower_case.resolution_mode.value,
            },
            "retell_llm_dynamic_variables": {
                "borrower_id": borrower_case.borrower_id,
                "borrower_name": borrower_profile.full_name,
                "lender_id": borrower_case.lender_id,
                "loan_id_masked": borrower_case.loan_id_masked,
                "amount_due": str(borrower_case.amount_due),
                "handoff_summary": handoff_summary or "",
            },
        }
        return self._post_json(config, "/v2/create-phone-call", payload)

    def verify_webhook_signature(self, raw_body: str, signature: str | None) -> None:
        config = self._config()
        if not config["webhook_verification_enabled"]:
            return
        if not signature:
            raise RetellWebhookVerificationError("Missing x-retell-signature header")
        retell_sdk = self._load_sdk()
        try:
            is_valid = bool(retell_sdk.verify(raw_body, config["api_key"], signature))
        except Exception as error:
            raise RetellWebhookVerificationError(f"Retell webhook verification failed: {error}") from error
        if not is_valid:
            raise RetellWebhookVerificationError("Invalid Retell webhook signature")

    def _assert_outbound_call_configured(self, config: dict[str, Any]) -> None:
        missing = []
        if not config["api_key"]:
            missing.append("RETELL_API_KEY")
        if not config["from_number"]:
            missing.append("RETELL_FROM_NUMBER")
        if not config["agent_id"]:
            missing.append("RETELL_AGENT_ID")
        if missing:
            raise RetellConfigurationError(
                "Retell outbound calling is not configured. Missing env vars: " + ", ".join(missing)
            )

    def _post_json(self, config: dict[str, Any], path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{config['base_url']}{path}"
        http_request = request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            response_body = ""
            try:
                response_body = error.read().decode("utf-8").strip()
            except Exception:
                response_body = ""
            raise RetellAPIError(
                f"Retell API request failed with HTTP {error.code} at {url}."
                + (f" Response: {response_body}" if response_body else "")
            ) from error
        except URLError as error:
            raise RetellAPIError(f"Retell API request failed for {url}: {error.reason}") from error

    def _normalize_phone_number(self, phone_number: str, *, label: str) -> str:
        normalized = "".join(char for char in phone_number.strip() if char.isdigit() or char == "+")
        if not normalized.startswith("+") or len(normalized) < 8:
            raise RetellConfigurationError(f"{label} must be in E.164 format. Received: {phone_number!r}")
        return normalized

    def _load_sdk(self):
        errors: list[str] = []
        for module_name in ("retell_sdk", "retell"):
            try:
                module = import_module(module_name)
            except ImportError as error:
                errors.append(str(error))
                continue
            retell_sdk = getattr(module, "Retell", None)
            if retell_sdk is not None:
                return retell_sdk
        raise RetellWebhookVerificationError(
            "Retell webhook verification requires the Python SDK to be installed"
            + (f" ({'; '.join(errors)})" if errors else "")
        )
