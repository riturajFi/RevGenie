from __future__ import annotations

from langchain_core.tools import StructuredTool

from app.services.borrower_profile import FileBorrowerProfileService
from app.services.compliance import FileComplianceService
from app.services.lender_policy import FileLenderPolicyService
from app.services.lender_profile import FileLenderProfileService
from app.services.loan import FileLoanService


def build_assessment_tools(lender_id: str) -> list[StructuredTool]:
    borrower_profile_service = FileBorrowerProfileService()
    compliance_service = FileComplianceService()
    lender_policy_service = FileLenderPolicyService()
    lender_profile_service = FileLenderProfileService()
    loan_service = FileLoanService()

    def get_borrower_information(borrower_id: str) -> dict:
        """Fetch the borrower profile for a borrower id."""
        borrower = borrower_profile_service.get_borrower_profile(borrower_id)
        if borrower is None:
            return {"found": False, "borrower_id": borrower_id}
        return {"found": True, "borrower": borrower.model_dump(mode="json")}

    def get_borrower_loan_for_lender(borrower_id: str) -> dict:
        """Fetch the loan for a borrower under the lender configured for this agent."""
        for loan in loan_service.list_loans():
            if loan.borrower_id == borrower_id and loan.lender_id == lender_id:
                return {"found": True, "loan": loan.model_dump(mode="json")}
        return {"found": False, "borrower_id": borrower_id, "lender_id": lender_id}

    def get_lender_information(lender_id_input: str) -> dict:
        """Fetch the lender profile for a lender id."""
        lender = lender_profile_service.get_lender_profile(lender_id_input)
        if lender is None:
            return {"found": False, "lender_id": lender_id_input}
        return {"found": True, "lender": lender.model_dump(mode="json")}

    def get_lender_policy(lender_id_input: str) -> dict:
        """Fetch the current lender policy for a lender id."""
        lender_policy = lender_policy_service.get_lender_policy(lender_id_input)
        if lender_policy is None:
            return {"found": False, "lender_id": lender_id_input}
        return {"found": True, "lender_policy": lender_policy.model_dump(mode="json")}

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
        StructuredTool.from_function(get_borrower_information),
        StructuredTool.from_function(get_borrower_loan_for_lender),
        StructuredTool.from_function(get_lender_information),
        # StructuredTool.from_function(get_lender_policy),
        StructuredTool.from_function(get_global_compliance_text),
        StructuredTool.from_function(get_lender_policy_text),
    ]
