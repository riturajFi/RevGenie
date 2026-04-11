from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.domain.lender_profile import LenderProfile
from app.services.lender_profile import FileLenderProfileService

router = APIRouter(prefix="/lender-profiles", tags=["lender-profiles"])
service = FileLenderProfileService()


class DeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool


@router.post("", response_model=LenderProfile, status_code=status.HTTP_201_CREATED)
def create_lender_profile(lender_profile: LenderProfile) -> LenderProfile:
    try:
        return service.create_lender_profile(lender_profile)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("", response_model=list[LenderProfile])
def list_lender_profiles() -> list[LenderProfile]:
    return service.list_lender_profiles()


@router.get("/{lender_id}", response_model=LenderProfile)
def get_lender_profile(lender_id: str) -> LenderProfile:
    lender_profile = service.get_lender_profile(lender_id)
    if lender_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lender profile not found")
    return lender_profile


@router.put("/{lender_id}", response_model=LenderProfile)
def update_lender_profile(lender_id: str, lender_profile: LenderProfile) -> LenderProfile:
    try:
        return service.update_lender_profile(lender_id, lender_profile)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete("/{lender_id}", response_model=DeleteResponse, status_code=status.HTTP_200_OK)
def delete_lender_profile(lender_id: str) -> DeleteResponse:
    deleted = service.delete_lender_profile(lender_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lender profile not found")
    return DeleteResponse(deleted=True)
