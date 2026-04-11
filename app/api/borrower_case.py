from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.domain.borrower_case import BorrowerCase
from app.services.borrower_case import FileBorrowerCaseService

router = APIRouter(prefix="/borrower-cases", tags=["borrower-cases"])
service = FileBorrowerCaseService()


class DeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool


@router.post("", response_model=BorrowerCase, status_code=status.HTTP_201_CREATED)
def create_borrower_case(borrower_case: BorrowerCase) -> BorrowerCase:
    try:
        return service.create_borrower_case(borrower_case)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("", response_model=list[BorrowerCase])
def list_borrower_cases() -> list[BorrowerCase]:
    return service.list_borrower_cases()


@router.get("/{borrower_id}", response_model=BorrowerCase)
def get_borrower_case(borrower_id: str) -> BorrowerCase:
    borrower_case = service.get_borrower_case(borrower_id)
    if borrower_case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrower case not found")
    return borrower_case


@router.put("/{borrower_id}", response_model=BorrowerCase)
def update_borrower_case(borrower_id: str, borrower_case: BorrowerCase) -> BorrowerCase:
    try:
        return service.update_borrower_case(borrower_id, borrower_case)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.delete("/{borrower_id}", response_model=DeleteResponse, status_code=status.HTTP_200_OK)
def delete_borrower_case(borrower_id: str) -> DeleteResponse:
    deleted = service.delete_borrower_case(borrower_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Borrower case not found")
    return DeleteResponse(deleted=True)
