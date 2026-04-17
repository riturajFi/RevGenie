from __future__ import annotations

import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain.borrower_case import BorrowerCase, CaseStatus, ContactChannel, ResolutionMode, Stage
from app.domain.borrower_profile import BorrowerProfile
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_profile import FileBorrowerProfileService


TARGET_BORROWER_ID = "b_001"
TARGET_BORROWER_NAME = "Aarav Sharma"
DEFAULT_PHONE_NUMBER = "+918917200633"

SCENARIO_DESCRIPTIONS = {
    "nira_hardship_settlement": "Fresh Agent 1 start for a Nira hardship settlement candidate with higher due amount.",
    "slice_payment_plan": "Fresh Agent 1 start for a Slice-style payment-plan candidate with lower due amount.",
    "nira_soft_recovery": "Fresh Agent 1 start for a lighter Nira recovery case with moderate dues.",
}


def _workflow_id(scenario_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"wf_{stamp}_{scenario_name}"


def _build_nira_hardship_settlement_case() -> BorrowerCase:
    borrower_case = BorrowerCase.model_validate(
        {
            "core": {
                "borrower_id": TARGET_BORROWER_ID,
                "workflow_id": _workflow_id("nira_hardship_settlement"),
                "loan_id_masked": "****4831",
                "lender_id": "nira",
                "stage": "ASSESSMENT",
                "case_status": "OPEN",
                "case_type": ["SETTLEMENT_CANDIDATE"],
                "amount_due": 12921,
                "identity_verified": True,
                "next_allowed_actions": ["OFFER_REDUCED_CLOSURE", "OFFER_PAYMENT_PLAN"],
                "final_disposition": None,
            },
            "attributes": {
                "assessment_notes": None,
                "borrower_capacity": {
                    "available_now": 2000,
                    "can_pay_later": True,
                    "can_pay_now": False,
                    "expected_date": "2026-04-20",
                },
                "borrower_intent": {
                    "protect_cibil": True,
                    "wants_full_closure": True,
                    "wants_settlement": True,
                },
                "borrower_objections": [],
                "borrower_stated_position": (
                    "Borrower confirmed they still cannot pay this month, hardship remains present, "
                    "and options can be reviewed around 2026-04-20."
                ),
                "contact_preferences": {
                    "channel_verification_discomfort": True,
                },
                "disclosures": {
                    "identity_disclosed": True,
                    "recording_disclosed": True,
                },
                "dispute_flags": {
                    "claims_paid": False,
                    "claims_wrong_commitment": False,
                },
                "dpd": 275,
                "final_notice_notes": None,
                "hardship_acknowledged": True,
                "hardship_flags": {
                    "emotional_distress": False,
                    "job_loss": True,
                    "medical_issue": True,
                    "student": True,
                },
                "last_contact_channel": "CHAT",
                "offers_made": [],
                "principal_outstanding": 10125,
                "resolution_call_id": None,
                "resolution_call_status": None,
                "resolution_mode": "VOICE",
                "resolution_notes": None,
                "stop_contact_flag": False,
            },
            "agent_context_summary": None,
            "latest_handoff_summary": None,
            "latest_handoff_stage": None,
        }
    )
    borrower_case.agent_context_summary = borrower_case.build_agent_context_summary()
    return borrower_case


def _build_from_template(template_borrower_id: str, *, scenario_name: str, resolution_mode: ResolutionMode) -> BorrowerCase:
    template_case = FileBorrowerCaseService().get_borrower_case(template_borrower_id)
    if template_case is None:
        raise SystemExit(f"Template case not found for {template_borrower_id}")

    borrower_case = BorrowerCase.model_validate(deepcopy(template_case.model_dump(mode="python")))
    borrower_case.borrower_id = TARGET_BORROWER_ID
    borrower_case.workflow_id = _workflow_id(scenario_name)
    borrower_case.stage = Stage.ASSESSMENT
    borrower_case.case_status = CaseStatus.OPEN
    borrower_case.final_disposition = None
    borrower_case.latest_handoff_stage = None
    borrower_case.latest_handoff_summary = None
    borrower_case.last_contact_channel = ContactChannel.CHAT
    borrower_case.resolution_mode = resolution_mode
    borrower_case.resolution_call_id = None
    borrower_case.resolution_call_status = None
    borrower_case.stop_contact_flag = False
    borrower_case.assessment_notes = None
    borrower_case.resolution_notes = None
    borrower_case.final_notice_notes = None
    borrower_case.agent_context_summary = borrower_case.build_agent_context_summary()
    return borrower_case


def _build_nira_soft_recovery_case() -> BorrowerCase:
    borrower_case = _build_nira_hardship_settlement_case()
    borrower_case.workflow_id = _workflow_id("nira_soft_recovery")
    borrower_case.amount_due = 7800
    borrower_case.principal_outstanding = 6200
    borrower_case.dpd = 86
    borrower_case.case_type = ["PAYMENT_PLAN_CANDIDATE"]
    borrower_case.next_allowed_actions = ["OFFER_PAYMENT_PLAN"]
    borrower_case.borrower_capacity = {
        "available_now": 1500,
        "can_pay_later": True,
        "can_pay_now": False,
        "expected_date": "2026-04-24",
    }
    borrower_case.borrower_intent = {
        "protect_cibil": True,
        "wants_full_closure": False,
        "wants_settlement": False,
    }
    borrower_case.hardship_flags = {
        "emotional_distress": False,
        "job_loss": False,
        "medical_issue": False,
        "student": False,
    }
    borrower_case.borrower_stated_position = (
        "Borrower says they cannot clear the full overdue amount today, but may manage a structured plan next week."
    )
    borrower_case.agent_context_summary = borrower_case.build_agent_context_summary()
    return borrower_case


def _build_case(scenario_name: str) -> BorrowerCase:
    if scenario_name == "nira_hardship_settlement":
        return _build_nira_hardship_settlement_case()
    if scenario_name == "slice_payment_plan":
        return _build_from_template(
            "b_002",
            scenario_name=scenario_name,
            resolution_mode=ResolutionMode.VOICE,
        )
    if scenario_name == "nira_soft_recovery":
        return _build_nira_soft_recovery_case()
    raise SystemExit(_usage())


def _upsert_profile(phone_number: str) -> BorrowerProfile:
    service = FileBorrowerProfileService()
    borrower_profile = BorrowerProfile(
        borrower_id=TARGET_BORROWER_ID,
        full_name=TARGET_BORROWER_NAME,
        phone_number=phone_number,
    )
    existing = service.get_borrower_profile(TARGET_BORROWER_ID)
    if existing is None:
        return service.create_borrower_profile(borrower_profile)
    return service.update_borrower_profile(TARGET_BORROWER_ID, borrower_profile)


def _upsert_case(borrower_case: BorrowerCase) -> BorrowerCase:
    service = FileBorrowerCaseService()
    existing = service.get_borrower_case(TARGET_BORROWER_ID)
    if existing is None:
        return service.create_borrower_case(borrower_case)
    return service.update_borrower_case(TARGET_BORROWER_ID, borrower_case)


def _usage() -> str:
    scenario_lines = "\n".join(f"  - {name}: {description}" for name, description in SCENARIO_DESCRIPTIONS.items())
    return (
        "Usage:\n"
        "  python3 scripts/seed_borrower_arav.py <scenario_name> [phone_number]\n"
        "  python3 scripts/seed_borrower_arav.py list\n\n"
        "Available scenarios:\n"
        f"{scenario_lines}\n"
    )


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        raise SystemExit(_usage())

    if sys.argv[1] == "list":
        print(_usage())
        return

    scenario_name = sys.argv[1].strip()
    phone_number = sys.argv[2].strip() if len(sys.argv) > 2 else DEFAULT_PHONE_NUMBER

    borrower_profile = _upsert_profile(phone_number)
    borrower_case = _build_case(scenario_name)
    borrower_case = _upsert_case(borrower_case)

    print(f"Seeded {TARGET_BORROWER_NAME} ({TARGET_BORROWER_ID})")
    print(f"scenario: {scenario_name}")
    print(f"phone_number: {borrower_profile.phone_number}")
    print(f"workflow_id: {borrower_case.workflow_id}")
    print(f"stage: {borrower_case.stage.value}")
    print(f"resolution_mode: {borrower_case.resolution_mode.value}")
    print(f"case_status: {borrower_case.case_status.value}")


if __name__ == "__main__":
    main()
