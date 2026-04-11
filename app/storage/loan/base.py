from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.loan import Loan


class LoanStorage(ABC):
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
