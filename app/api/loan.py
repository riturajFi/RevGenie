from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.domain.loan import Loan
from app.services.loan import FileLoanService

router = APIRouter(prefix="/loans", tags=["loans"])
service = FileLoanService()


class DeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted: bool


@router.post("", response_model=Loan, status_code=status.HTTP_201_CREATED)
def create_loan(loan: Loan) -> Loan:
    try:
        return service.create_loan(loan)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

@router.get("", response_model=list[Loan])
def list_loans() -> list[Loan]:
    return service.list_loans()

@router.get("/{account_id}", response_model=Loan)
def get_loan(account_id: str) -> Loan:
    loan = service.get_loan(account_id)
    if loan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    return loan

@router.put("/{account_id}", response_model=Loan)
def update_loan(account_id: str, loan: Loan) -> Loan:
    try:
        return service.update_loan(account_id, loan)
    except KeyError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

@router.delete("/{account_id}", response_model=DeleteResponse, status_code=status.HTTP_200_OK)
def delete_loan(account_id: str) -> DeleteResponse:
    deleted = service.delete_loan(account_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Loan not found")
    return DeleteResponse(deleted=True)
