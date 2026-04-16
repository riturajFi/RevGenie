from __future__ import annotations

import json
import os
from importlib import import_module
from typing import Any
from urllib import request

from app.domain.borrower_case import BorrowerCase
from app.domain.borrower_profile import BorrowerProfile


class RetellConfigurationError(RuntimeError):
    pass


class RetellWebhookVerificationError(RuntimeError):
    pass


class RetellService:
    def __init__(self) -> None:
        self.base_url = os.getenv("RETELL_BASE_URL", "https://api.retellai.com").rstrip("/")
        self.api_key = os.getenv("RETELL_API_KEY", "").strip()
        self.agent_id = os.getenv("RETELL_AGENT_ID", "").strip()
        self.from_number = os.getenv("RETELL_FROM_NUMBER", "").strip()
        self.webhook_verification_enabled = (
            os.getenv("RETELL_VALIDATE_SIGNATURES", "false").strip().lower() in {"1", "true", "yes", "on"}
        )

    def place_phone_call(
        self,
        borrower_case: BorrowerCase,
        borrower_profile: BorrowerProfile,
        handoff_summary: str | None,
    ) -> dict[str, Any]:
        self._assert_outbound_call_configured()
        payload = {
            "from_number": self.from_number,
            "to_number": borrower_profile.phone_number,
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
        if self.agent_id:
            payload["override_agent_id"] = self.agent_id
        return self._post_json("/v2/create-phone-call", payload)

    def verify_webhook_signature(self, raw_body: str, signature: str | None) -> None:
        if not self.webhook_verification_enabled:
            return
        if not signature:
            raise RetellWebhookVerificationError("Missing x-retell-signature header")
        retell_sdk = self._load_sdk()
        try:
            is_valid = bool(retell_sdk.verify(raw_body, self.api_key, signature))
        except Exception as error:
            raise RetellWebhookVerificationError(f"Retell webhook verification failed: {error}") from error
        if not is_valid:
            raise RetellWebhookVerificationError("Invalid Retell webhook signature")

    def _assert_outbound_call_configured(self) -> None:
        missing = []
        if not self.api_key:
            missing.append("RETELL_API_KEY")
        if not self.from_number:
            missing.append("RETELL_FROM_NUMBER")
        if missing:
            raise RetellConfigurationError(
                "Retell outbound calling is not configured. Missing env vars: " + ", ".join(missing)
            )

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        http_request = request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(http_request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

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
