from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.domain.borrower_profile import BorrowerProfile
from app.services.borrower_profile import FileBorrowerProfileService

router = APIRouter(prefix="/borrower-profiles", tags=["borrower-profiles"])
service = FileBorrowerProfileService()


class DeleteResponse(BaseModel):
    deleted: bool


class CreateBorrowerProfileRequest(BaseModel):
    full_name: str
    phone_number: str


def _generate_borrower_id() -> str:
    while True:
        candidate = f"b_{uuid4().hex[:8]}"
        if service.get_borrower_profile(candidate) is None:
            return candidate


@router.post("", response_model=BorrowerProfile, status_code=status.HTTP_201_CREATED)
def create_borrower_profile(request: CreateBorrowerProfileRequest) -> BorrowerProfile:
    try:
        borrower_profile = BorrowerProfile(
            borrower_id=_generate_borrower_id(),
            full_name=request.full_name,
            phone_number=request.phone_number,
        )
        return service.create_borrower_profile(borrower_profile)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("", response_model=list[BorrowerProfile])
def list_borrower_profiles() -> list[BorrowerProfile]:
    return service.list_borrower_profiles()


@router.get("/{borrower_id}", response_model=BorrowerProfile)
def get_borrower_profile(borrower_id: str) -> BorrowerProfile:
    borrower_profile = service.get_borrower_profile(borrower_id)
    if borrower_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrower profile not found")
    return borrower_profile


@router.put("/{borrower_id}", response_model=BorrowerProfile)
def update_borrower_profile(borrower_id: str, borrower_profile: BorrowerProfile) -> BorrowerProfile:
    try:
        return service.update_borrower_profile(borrower_id, borrower_profile)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete("/{borrower_id}", response_model=DeleteResponse, status_code=status.HTTP_200_OK)
def delete_borrower_profile(borrower_id: str) -> DeleteResponse:
    deleted = service.delete_borrower_profile(borrower_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrower profile not found")
    return DeleteResponse(deleted=True)
