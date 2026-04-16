from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.domain.borrower_case import BorrowerCase
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

    borrower_case = borrower_case_service.get_borrower_case(borrower_profile.borrower_id)
    if borrower_case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Borrower case not found",
        )

    return BorrowerLoginResponse(
        borrower_profile=borrower_profile,
        borrower_case=borrower_case,
    )
