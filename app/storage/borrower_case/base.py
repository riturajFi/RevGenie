from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.borrower_case import BorrowerCase


class BorrowerCaseStorage(ABC):
    @abstractmethod
    def create_borrower_case(self, borrower_case: BorrowerCase) -> BorrowerCase:
        raise NotImplementedError

    @abstractmethod
    def get_borrower_case(self, borrower_id: str) -> BorrowerCase | None:
        raise NotImplementedError

    @abstractmethod
    def list_borrower_cases(self) -> list[BorrowerCase]:
        raise NotImplementedError

    @abstractmethod
    def update_borrower_case(self, borrower_id: str, borrower_case: BorrowerCase) -> BorrowerCase:
        raise NotImplementedError

    @abstractmethod
    def delete_borrower_case(self, borrower_id: str) -> bool:
        raise NotImplementedError
