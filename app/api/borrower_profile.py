from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.domain.borrower_profile import BorrowerProfile
from app.services.borrower_profile import FileBorrowerProfileService

router = APIRouter(prefix="/borrower-profiles", tags=["borrower-profiles"])
service = FileBorrowerProfileService()


@router.post("", response_model=BorrowerProfile, status_code=status.HTTP_201_CREATED)
def create_borrower_profile(borrower_profile: BorrowerProfile) -> BorrowerProfile:
    try:
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


@router.delete("/{borrower_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_borrower_profile(borrower_id: str) -> None:
    deleted = service.delete_borrower_profile(borrower_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrower profile not found")
