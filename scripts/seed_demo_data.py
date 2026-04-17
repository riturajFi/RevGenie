from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain.borrower_case import BorrowerCase, CaseStatus, ResolutionMode, Stage
from app.domain.borrower_profile import BorrowerProfile
from app.domain.lender_profile import LenderProfile
from app.domain.lender_policy import LenderPolicy
from app.domain.loan import Loan
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_profile import FileBorrowerProfileService
from app.services.lender_policy import FileLenderPolicyService
from app.services.lender_profile import FileLenderProfileService
from app.services.loan import FileLoanService


borrowers = [
    BorrowerProfile(
        borrower_id="b_001",
        full_name="Aarav Sharma",
        phone_number="+919900000001",
    ),
    BorrowerProfile(
        borrower_id="b_002",
        full_name="Neha Verma",
        phone_number="+919900000002",
    ),
    BorrowerProfile(
        borrower_id="b_003",
        full_name="Rohit Iyer",
        phone_number="+919900000003",
    ),
]

lenders = [
    LenderProfile(lender_id="nira", lender_name="Nira Finance"),
    LenderProfile(lender_id="slice", lender_name="Slice"),
]

lender_policies = [
    LenderPolicy(
        lender_id="nira",
        policy="We do not provide extensions beyond 30 days. Reduced closure and structured payment plans require policy-compliant approvals only.",
    ),
    LenderPolicy(
        lender_id="slice",
        policy="We do not provide extensions beyond 21 days. Payment plans may be discussed only within approved policy bands.",
    ),
]

loans = [
    Loan(account_id="acc_001", borrower_id="b_001", lender_id="nira", amount_due=12921),
    Loan(account_id="acc_002", borrower_id="b_002", lender_id="slice", amount_due=8400),
    Loan(account_id="acc_003", borrower_id="b_003", lender_id="nira", amount_due=22500),
]

borrower_cases = [
    BorrowerCase.model_validate(
        {
            "core": {
                "borrower_id": "b_001",
                "workflow_id": "wf_001",
                "loan_id_masked": "****4831",
                "lender_id": "nira",
                "stage": Stage.ASSESSMENT,
                "case_status": CaseStatus.OPEN,
                "amount_due": 12921,
                "final_disposition": None,
            },
            "attributes": {
                "resolution_mode": ResolutionMode.VOICE.value,
            },
        }
    ),
    BorrowerCase.model_validate(
        {
            "core": {
                "borrower_id": "b_002",
                "workflow_id": "wf_002",
                "loan_id_masked": "****1184",
                "lender_id": "slice",
                "stage": Stage.ASSESSMENT,
                "case_status": CaseStatus.OPEN,
                "amount_due": 8400,
                "final_disposition": None,
            },
            "attributes": {
                "resolution_mode": ResolutionMode.VOICE.value,
            },
        }
    ),
    BorrowerCase.model_validate(
        {
            "core": {
                "borrower_id": "b_003",
                "workflow_id": "wf_003",
                "loan_id_masked": "****9007",
                "lender_id": "nira",
                "stage": Stage.FINAL_NOTICE,
                "case_status": CaseStatus.OPEN,
                "amount_due": 22500,
                "final_disposition": None,
            },
            "attributes": {
                "resolution_mode": ResolutionMode.VOICE.value,
            },
        }
    ),
]


def upsert_borrowers() -> None:
    service = FileBorrowerProfileService()
    for borrower in borrowers:
        existing = service.get_borrower_profile(borrower.borrower_id)
        if existing is None:
            service.create_borrower_profile(borrower)
        else:
            service.update_borrower_profile(borrower.borrower_id, borrower)


def upsert_lenders() -> None:
    service = FileLenderProfileService()
    for lender in lenders:
        existing = service.get_lender_profile(lender.lender_id)
        if existing is None:
            service.create_lender_profile(lender)
        else:
            service.update_lender_profile(lender.lender_id, lender)


def upsert_lender_policies() -> None:
    service = FileLenderPolicyService()
    for lender_policy in lender_policies:
        existing = service.get_lender_policy(lender_policy.lender_id)
        if existing is None:
            service.create_lender_policy(lender_policy)
        else:
            service.update_lender_policy(lender_policy.lender_id, lender_policy)


def upsert_loans() -> None:
    service = FileLoanService()
    for loan in loans:
        existing = service.get_loan(loan.account_id)
        if existing is None:
            service.create_loan(loan)
        else:
            service.update_loan(loan.account_id, loan)


def upsert_borrower_cases() -> None:
    service = FileBorrowerCaseService()
    for borrower_case in borrower_cases:
        existing = service.get_borrower_case(borrower_case.borrower_id)
        if existing is None:
            service.create_borrower_case(borrower_case)
        else:
            service.update_borrower_case(borrower_case.borrower_id, borrower_case)


def main() -> None:
    upsert_borrowers()
    upsert_lenders()
    upsert_lender_policies()
    upsert_loans()
    upsert_borrower_cases()
    print("Seeded borrowers, lenders, lender policies, loans, and borrower cases.")


if __name__ == "__main__":
    main()
