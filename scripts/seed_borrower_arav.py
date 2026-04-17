from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain.borrower_case import BorrowerCase, CaseStatus, ResolutionMode, Stage
from app.domain.borrower_profile import BorrowerProfile
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_profile import FileBorrowerProfileService


TARGET_BORROWER_ID = "b_001"
TARGET_BORROWER_NAME = "Aarav Sharma"
DEFAULT_PHONE_NUMBER = "+918917200633"

SCENARIO_DESCRIPTIONS = {
    "nira_hardship_settlement": "Fresh Agent 1 start for a Nira account with higher dues.",
    "slice_payment_plan": "Fresh Agent 1 start for a Slice account with mid-range dues.",
    "nira_soft_recovery": "Fresh Agent 1 start for a lighter Nira recovery case.",
}


def _workflow_id(scenario_name: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"wf_{stamp}_{scenario_name}"


def _build_case(*, scenario_name: str, lender_id: str, loan_id_masked: str, amount_due: int) -> BorrowerCase:
    return BorrowerCase.model_validate(
        {
            "core": {
                "borrower_id": TARGET_BORROWER_ID,
                "workflow_id": _workflow_id(scenario_name),
                "loan_id_masked": loan_id_masked,
                "lender_id": lender_id,
                "stage": Stage.ASSESSMENT,
                "case_status": CaseStatus.OPEN,
                "amount_due": amount_due,
                "final_disposition": None,
            },
            "attributes": {
                "resolution_mode": ResolutionMode.VOICE.value,
            },
            "latest_handoff_summary": None,
        }
    )


def _build_scenario_case(scenario_name: str) -> BorrowerCase:
    if scenario_name == "nira_hardship_settlement":
        return _build_case(
            scenario_name=scenario_name,
            lender_id="nira",
            loan_id_masked="****4831",
            amount_due=12921,
        )
    if scenario_name == "slice_payment_plan":
        return _build_case(
            scenario_name=scenario_name,
            lender_id="slice",
            loan_id_masked="****1184",
            amount_due=8400,
        )
    if scenario_name == "nira_soft_recovery":
        return _build_case(
            scenario_name=scenario_name,
            lender_id="nira",
            loan_id_masked="****7620",
            amount_due=7800,
        )
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
    borrower_case = _build_scenario_case(scenario_name)
    borrower_case = _upsert_case(borrower_case)

    print(f"Seeded {TARGET_BORROWER_NAME} ({TARGET_BORROWER_ID})")
    print(f"scenario: {scenario_name}")
    print(f"phone_number: {borrower_profile.phone_number}")
    print(f"workflow_id: {borrower_case.workflow_id}")
    print(f"lender_id: {borrower_case.lender_id}")
    print(f"loan_id_masked: {borrower_case.loan_id_masked}")
    print(f"amount_due: {borrower_case.amount_due}")
    print(f"stage: {borrower_case.stage.value}")
    print(f"resolution_mode: {borrower_case.resolution_mode.value}")
    print(f"case_status: {borrower_case.case_status.value}")


if __name__ == "__main__":
    main()
