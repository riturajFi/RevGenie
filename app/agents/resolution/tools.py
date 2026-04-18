from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from langchain_core.tools import StructuredTool

from app.services.borrower_profile import FileBorrowerProfileService
from app.services.lender_policy import FileLenderPolicyService
from app.services.lender_profile import FileLenderProfileService
from app.services.loan import FileLoanService


RESOLUTION_POLICY_RULES = {
    "nira": {
        "plan_window_days": 30,
        "first_payment_window_days": 3,
        "reduced_closure_ratio": Decimal("0.88"),
        "reduced_closure_window_days": 7,
    },
    "slice": {
        "plan_window_days": 21,
        "first_payment_window_days": 3,
        "reduced_closure_ratio": Decimal("0.92"),
        "reduced_closure_window_days": 5,
    },
}


def _round_currency(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_date_input(value: str | None) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    formats = (
        "%Y-%m-%d",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%d-%m-%Y",
        "%d/%m/%Y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def build_resolution_tools(lender_id: str) -> list[StructuredTool]:
    borrower_profile_service = FileBorrowerProfileService()
    lender_profile_service = FileLenderProfileService()
    lender_policy_service = FileLenderPolicyService()
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

    def get_resolution_options(
        borrower_id: str,
        proposed_first_payment_amount: float | None = None,
        proposed_second_payment_amount: float | None = None,
        proposed_second_payment_date: str | None = None,
    ) -> dict:
        """Compute exact policy-backed resolution options and validate a proposed plan for this lender."""
        rules = RESOLUTION_POLICY_RULES.get(lender_id)
        if rules is None:
            return {"found": False, "borrower_id": borrower_id, "lender_id": lender_id, "reason": "Unsupported lender"}

        loan_record = None
        for loan in loan_service.list_loans():
            if loan.borrower_id == borrower_id and loan.lender_id == lender_id:
                loan_record = loan
                break
        if loan_record is None:
            return {"found": False, "borrower_id": borrower_id, "lender_id": lender_id, "reason": "Loan not found"}

        offer_date = date.today()
        amount_due = Decimal(str(loan_record.amount_due))
        reduced_closure_amount = _round_currency(amount_due * rules["reduced_closure_ratio"])
        latest_first_payment_date = offer_date + timedelta(days=rules["first_payment_window_days"])
        latest_second_payment_date = offer_date + timedelta(days=rules["plan_window_days"])

        response = {
            "found": True,
            "borrower_id": borrower_id,
            "lender_id": lender_id,
            "loan": loan_record.model_dump(mode="json"),
            "offer_date": offer_date.isoformat(),
            "structured_plan": {
                "max_payments": 2,
                "first_payment_due_within_days": rules["first_payment_window_days"],
                "final_payment_due_within_days": rules["plan_window_days"],
                "latest_first_payment_date": latest_first_payment_date.isoformat(),
                "latest_final_payment_date": latest_second_payment_date.isoformat(),
            },
            "reduced_closure": {
                "amount": float(reduced_closure_amount),
                "ratio": float(rules["reduced_closure_ratio"]),
                "due_within_days": rules["reduced_closure_window_days"],
                "latest_payment_date": (offer_date + timedelta(days=rules["reduced_closure_window_days"])).isoformat(),
            },
        }

        if proposed_first_payment_amount is None and proposed_second_payment_amount is None and not proposed_second_payment_date:
            return response

        validation_errors: list[str] = []
        first_amount = Decimal(str(proposed_first_payment_amount or 0))
        second_amount = Decimal(str(proposed_second_payment_amount or 0))
        parsed_second_date = _parse_date_input(proposed_second_payment_date)

        if first_amount <= 0:
            validation_errors.append("First payment amount must be greater than 0.")
        if second_amount <= 0:
            validation_errors.append("Second payment amount must be greater than 0.")
        if parsed_second_date is None:
            validation_errors.append("Second payment date could not be parsed.")
        if parsed_second_date and parsed_second_date > latest_second_payment_date:
            validation_errors.append(
                f"Second payment date must be on or before {latest_second_payment_date.isoformat()}."
            )

        expected_second_amount = _round_currency(amount_due - first_amount)
        if first_amount > 0 and second_amount > 0 and _round_currency(second_amount) != expected_second_amount:
            validation_errors.append(
                f"Second payment amount must be {expected_second_amount} when first payment is {first_amount}."
            )

        response["proposal_validation"] = {
            "valid": not validation_errors,
            "first_payment_amount": float(_round_currency(first_amount)),
            "second_payment_amount": float(_round_currency(second_amount)),
            "second_payment_date": parsed_second_date.isoformat() if parsed_second_date else None,
            "expected_second_payment_amount": float(expected_second_amount),
            "errors": validation_errors,
        }
        return response

    return [
        StructuredTool.from_function(get_borrower_information),
        StructuredTool.from_function(get_borrower_loan_for_lender),
        StructuredTool.from_function(get_lender_information),
        StructuredTool.from_function(get_lender_policy),
        StructuredTool.from_function(get_resolution_options),
    ]
