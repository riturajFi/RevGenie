from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.domain.lender_policy import LenderPolicy
from app.services.lender_policy import FileLenderPolicyService

router = APIRouter(prefix="/lender-policies", tags=["lender-policies"])
service = FileLenderPolicyService()


class DeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool


@router.post("", response_model=LenderPolicy, status_code=status.HTTP_201_CREATED)
def create_lender_policy(lender_policy: LenderPolicy) -> LenderPolicy:
    try:
        return service.create_lender_policy(lender_policy)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("", response_model=list[LenderPolicy])
def list_lender_policies() -> list[LenderPolicy]:
    return service.list_lender_policies()


@router.get("/{lender_id}", response_model=LenderPolicy)
def get_lender_policy(lender_id: str) -> LenderPolicy:
    lender_policy = service.get_lender_policy(lender_id)
    if lender_policy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lender policy not found")
    return lender_policy


@router.put("/{lender_id}", response_model=LenderPolicy)
def update_lender_policy(lender_id: str, lender_policy: LenderPolicy) -> LenderPolicy:
    try:
        return service.update_lender_policy(lender_id, lender_policy)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete("/{lender_id}", response_model=DeleteResponse, status_code=status.HTTP_200_OK)
def delete_lender_policy(lender_id: str) -> DeleteResponse:
    deleted = service.delete_lender_policy(lender_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lender policy not found")
    return DeleteResponse(deleted=True)
