from __future__ import annotations

from langchain_core.tools import StructuredTool

from app.services.compliance import FileComplianceService
from app.services.lender_policy import FileLenderPolicyService


def build_resolution_tools(lender_id: str) -> list[StructuredTool]:
    compliance_service = FileComplianceService()
    lender_policy_service = FileLenderPolicyService()
    def get_global_compliance_text() -> dict:
        """Fetch the global compliance rules as plain text."""
        return {"found": True, "rules_text": compliance_service.get_rules_text()}

    def get_lender_policy_text(lender_id_input: str) -> dict:
        """Fetch the lender policy as plain text."""
        lender_policy = lender_policy_service.get_lender_policy(lender_id_input)
        if lender_policy is None:
            return {"found": False, "lender_id": lender_id_input}
        return {"found": True, "policy_text": lender_policy.policy}

    return [
        # StructuredTool.from_function(get_global_compliance_text),
        StructuredTool.from_function(get_lender_policy_text),
    ]
