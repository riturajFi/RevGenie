from __future__ import annotations

from datetime import datetime, timezone
import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.domain.borrower_case import BorrowerCase, CaseStatus, Stage
from app.domain.borrower_profile import BorrowerProfile
from app.services.borrower_case import FileBorrowerCaseService
from app.services.borrower_profile import FileBorrowerProfileService


router = APIRouter(prefix="/borrower-auth", tags=["borrower-auth"])
borrower_profile_service = FileBorrowerProfileService()
borrower_case_service = FileBorrowerCaseService()


class BorrowerLoginRequest(BaseModel):
    phone_number: str
    password: str


class BorrowerLoginResponse(BaseModel):
    borrower_profile: BorrowerProfile
    borrower_case: BorrowerCase


def _normalize_phone_number(phone_number: str) -> str:
    return "".join(char for char in phone_number.strip() if char.isdigit() or char == "+")


def _assert_borrower_portal_password(password: str) -> None:
    expected_password = os.getenv("BORROWER_PORTAL_PASSWORD", "").strip()
    if not expected_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="BORROWER_PORTAL_PASSWORD is not configured",
        )
    if password != expected_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid borrower credentials",
        )


def _generate_workflow_id() -> str:
    return f"wf_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"


def _reset_borrower_case(borrower_case: BorrowerCase) -> BorrowerCase:
    previous_resolution_mode = borrower_case.resolution_mode
    borrower_case.workflow_id = _generate_workflow_id()
    borrower_case.stage = Stage.ASSESSMENT
    borrower_case.case_status = CaseStatus.OPEN
    borrower_case.final_disposition = None
    borrower_case.latest_handoff_summary = None
    borrower_case.attributes = {}
    borrower_case.resolution_mode = previous_resolution_mode
    borrower_case.resolution_call_id = None
    borrower_case.resolution_call_status = None
    borrower_case.prompt_version_overrides = {}
    borrower_case.simulation_uniqueness_tag = None
    return borrower_case_service.update_borrower_case(borrower_case.borrower_id, borrower_case)


def _print_loaded_borrower_context(*, action: str, borrower_profile: BorrowerProfile, borrower_case: BorrowerCase) -> None:
    print(f"[borrower_auth:{action}] borrower_profile={borrower_profile.model_dump(mode='json')}")
    print(f"[borrower_auth:{action}] borrower_case={borrower_case.model_dump(mode='json')}")


def _load_profile_and_case_by_borrower_id(borrower_id: str) -> tuple[BorrowerProfile, BorrowerCase]:
    borrower_profile = borrower_profile_service.get_borrower_profile(borrower_id)
    if borrower_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borrower profile not found",
        )
    borrower_case = borrower_case_service.get_borrower_case(borrower_id)
    if borrower_case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borrower case not found",
        )
    return borrower_profile, borrower_case


@router.post("/login", response_model=BorrowerLoginResponse)
def borrower_login(request: BorrowerLoginRequest) -> BorrowerLoginResponse:
    _assert_borrower_portal_password(request.password)
    normalized_phone_number = _normalize_phone_number(request.phone_number)
    if not normalized_phone_number:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Phone number is required",
        )

    borrower_profile = next(
        (
            profile
            for profile in borrower_profile_service.list_borrower_profiles()
            if _normalize_phone_number(profile.phone_number) == normalized_phone_number
        ),
        None,
    )
    if borrower_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borrower not found for this phone number",
        )

    _, borrower_case = _load_profile_and_case_by_borrower_id(borrower_profile.borrower_id)
    borrower_case = _reset_borrower_case(borrower_case)
    _print_loaded_borrower_context(
        action="login",
        borrower_profile=borrower_profile,
        borrower_case=borrower_case,
    )

    return BorrowerLoginResponse(
        borrower_profile=borrower_profile,
        borrower_case=borrower_case,
    )


@router.post("/reset/{borrower_id}", response_model=BorrowerLoginResponse)
def reset_borrower_session(borrower_id: str) -> BorrowerLoginResponse:
    borrower_profile, borrower_case = _load_profile_and_case_by_borrower_id(borrower_id)
    borrower_case = _reset_borrower_case(borrower_case)
    _print_loaded_borrower_context(
        action="reset",
        borrower_profile=borrower_profile,
        borrower_case=borrower_case,
    )
    return BorrowerLoginResponse(
        borrower_profile=borrower_profile,
        borrower_case=borrower_case,
    )
