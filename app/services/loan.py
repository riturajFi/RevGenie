from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.loan import Loan
from app.storage.loan.base import LoanStorage
from app.storage.loan.json_file import JsonFileLoanStorage


class LoanService(ABC):
    @abstractmethod
    def create_loan(self, loan: Loan) -> Loan:
        raise NotImplementedError

    @abstractmethod
    def get_loan(self, account_id: str) -> Loan | None:
        raise NotImplementedError

    @abstractmethod
    def list_loans(self) -> list[Loan]:
        raise NotImplementedError

    @abstractmethod
    def update_loan(self, account_id: str, loan: Loan) -> Loan:
        raise NotImplementedError

    @abstractmethod
    def delete_loan(self, account_id: str) -> bool:
        raise NotImplementedError


class FileLoanService(LoanService):
    def __init__(self, file_path: str = "data/loans.json") -> None:
        self.storage: LoanStorage = JsonFileLoanStorage(file_path)

    def create_loan(self, loan: Loan) -> Loan:
        return self.storage.create_loan(loan)

    def get_loan(self, account_id: str) -> Loan | None:
        return self.storage.get_loan(account_id)

    def list_loans(self) -> list[Loan]:
        return self.storage.list_loans()

    def update_loan(self, account_id: str, loan: Loan) -> Loan:
        return self.storage.update_loan(account_id, loan)

    def delete_loan(self, account_id: str) -> bool:
        return self.storage.delete_loan(account_id)
