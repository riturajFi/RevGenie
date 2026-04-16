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
from app.services.retell import RetellService

load_env_file()


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python3 scripts/start_resolution_voice_call.py <borrower_id>")

    borrower_id = sys.argv[1]
    borrower_case = FileBorrowerCaseService().get_borrower_case(borrower_id)
    if borrower_case is None:
        raise SystemExit(f"Borrower case not found for {borrower_id}")

    borrower_profile = FileBorrowerProfileService().get_borrower_profile(borrower_id)
    if borrower_profile is None:
        raise SystemExit(f"Borrower profile not found for {borrower_id}")

    result = RetellService().place_phone_call(
        borrower_case=borrower_case,
        borrower_profile=borrower_profile,
        handoff_summary=borrower_case.latest_handoff_summary,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
