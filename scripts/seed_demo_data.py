from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain.borrower_case import (
    ApprovalState,
    BorrowerCapacity,
    BorrowerCase,
    BorrowerIntent,
    CaseStatus,
    ContactChannel,
    DisputeFlags,
    HardshipFlags,
    Stage,
)
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
    BorrowerCase(
        borrower_id="b_001",
        workflow_id="wf_001",
        loan_id_masked="****4831",
        lender_id="nira",
        stage=Stage.ASSESSMENT,
        case_status=CaseStatus.OPEN,
        case_type=["SETTLEMENT_CANDIDATE"],
        amount_due=12921,
        principal_outstanding=10125,
        dpd=275,
        borrower_capacity=BorrowerCapacity(
            can_pay_now=False,
            available_now=6000,
            can_pay_later=True,
            expected_date="2026-04-20",
        ),
        borrower_intent=BorrowerIntent(
            wants_settlement=True,
            wants_full_closure=True,
            protect_cibil=True,
        ),
        hardship_flags=HardshipFlags(
            job_loss=True,
            medical_issue=False,
            student=True,
            emotional_distress=False,
        ),
        dispute_flags=DisputeFlags(
            claims_paid=False,
            claims_wrong_commitment=False,
        ),
        approval_state=ApprovalState(
            required=True,
            type="PENALTY_WAIVER",
            status="APPROVED",
        ),
        offers_made=[],
        next_allowed_actions=["OFFER_REDUCED_CLOSURE", "OFFER_PAYMENT_PLAN"],
        stop_contact_flag=False,
        identity_verified=True,
        last_contact_channel=ContactChannel.CHAT,
    ),
    BorrowerCase(
        borrower_id="b_002",
        workflow_id="wf_002",
        loan_id_masked="****1184",
        lender_id="slice",
        stage=Stage.ASSESSMENT,
        case_status=CaseStatus.OPEN,
        case_type=["PAYMENT_PLAN_CANDIDATE"],
        amount_due=8400,
        principal_outstanding=7000,
        dpd=94,
        borrower_capacity=BorrowerCapacity(
            can_pay_now=True,
            available_now=2000,
            can_pay_later=True,
            expected_date="2026-04-25",
        ),
        borrower_intent=BorrowerIntent(
            wants_settlement=False,
            wants_full_closure=False,
            protect_cibil=True,
        ),
        hardship_flags=HardshipFlags(
            job_loss=False,
            medical_issue=False,
            student=False,
            emotional_distress=False,
        ),
        dispute_flags=DisputeFlags(
            claims_paid=False,
            claims_wrong_commitment=False,
        ),
        approval_state=ApprovalState(
            required=False,
            type=None,
            status=None,
        ),
        offers_made=[],
        next_allowed_actions=["OFFER_PAYMENT_PLAN"],
        stop_contact_flag=False,
        identity_verified=False,
        last_contact_channel=ContactChannel.CHAT,
    ),
    BorrowerCase(
        borrower_id="b_003",
        workflow_id="wf_003",
        loan_id_masked="****9007",
        lender_id="nira",
        stage=Stage.FINAL_NOTICE,
        case_status=CaseStatus.OPEN,
        case_type=["FINAL_NOTICE"],
        amount_due=22500,
        principal_outstanding=18000,
        dpd=320,
        borrower_capacity=BorrowerCapacity(
            can_pay_now=False,
            available_now=0,
            can_pay_later=False,
            expected_date=None,
        ),
        borrower_intent=BorrowerIntent(
            wants_settlement=False,
            wants_full_closure=False,
            protect_cibil=False,
        ),
        hardship_flags=HardshipFlags(
            job_loss=False,
            medical_issue=True,
            student=False,
            emotional_distress=False,
        ),
        dispute_flags=DisputeFlags(
            claims_paid=False,
            claims_wrong_commitment=True,
        ),
        approval_state=ApprovalState(
            required=True,
            type="SPECIAL_SETTLEMENT",
            status="PENDING",
        ),
        offers_made=[],
        next_allowed_actions=["SEND_FINAL_NOTICE", "FLAG_FOR_REVIEW"],
        stop_contact_flag=False,
        identity_verified=True,
        last_contact_channel=ContactChannel.VOICE,
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
