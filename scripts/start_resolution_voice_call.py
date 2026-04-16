from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from env_loader import load_env_file
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_profile import FileBorrowerProfileService
from app.services.retell import RetellAPIError, RetellConfigurationError, RetellService

load_env_file()


def _mask(value: str) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _print_section(title: str) -> None:
    print(f"\n== {title} ==")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python3 scripts/start_resolution_voice_call.py <borrower_id>")

    borrower_id = sys.argv[1]
    service = RetellService()
    borrower_case = FileBorrowerCaseService().get_borrower_case(borrower_id)
    if borrower_case is None:
        raise SystemExit(f"Borrower case not found for {borrower_id}")

    borrower_profile = FileBorrowerProfileService().get_borrower_profile(borrower_id)
    if borrower_profile is None:
        raise SystemExit(f"Borrower profile not found for {borrower_id}")

    config = service._config()
    from_number = "".join(char for char in config["from_number"].strip() if char.isdigit() or char == "+")
    to_number = "".join(char for char in borrower_profile.phone_number.strip() if char.isdigit() or char == "+")

    _print_section("Borrower")
    print(f"borrower_id: {borrower_case.borrower_id}")
    print(f"name: {borrower_profile.full_name}")
    print(f"stage: {borrower_case.stage.value}")
    print(f"resolution_mode: {borrower_case.resolution_mode.value}")
    print(f"workflow_id: {borrower_case.workflow_id}")

    _print_section("Phone Numbers")
    print(f"from_number_raw: {config['from_number'] or '<missing>'}")
    print(f"from_number_normalized: {from_number or '<missing>'}")
    print(f"to_number_raw: {borrower_profile.phone_number or '<missing>'}")
    print(f"to_number_normalized: {to_number or '<missing>'}")

    _print_section("Retell Config")
    print(f"base_url: {config['base_url']}")
    print(f"api_key: {_mask(config['api_key'])}")
    print(f"agent_id: {config['agent_id'] or '<missing>'}")
    print(f"validate_signatures: {config['webhook_verification_enabled']}")

    _print_section("Handoff")
    print((borrower_case.latest_handoff_summary or "<missing>")[:500])

    _print_section("Call Attempt")
    try:
        result = service.place_phone_call(
            borrower_case=borrower_case,
            borrower_profile=borrower_profile,
            handoff_summary=borrower_case.latest_handoff_summary,
        )
    except (RetellConfigurationError, RetellAPIError) as error:
        print(f"FAILED: {error}")
        raise SystemExit(1) from error

    print("SUCCESS")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
