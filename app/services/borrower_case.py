from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.borrower_case import BorrowerCase
from app.storage.borrower_case.base import BorrowerCaseStorage
from app.storage.borrower_case.json_file import JsonFileBorrowerCaseStorage


class BorrowerCaseService(ABC):
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


class FileBorrowerCaseService(BorrowerCaseService):
    def __init__(self, file_path: str = "data/app/borrower_cases.json") -> None:
        self.storage: BorrowerCaseStorage = JsonFileBorrowerCaseStorage(file_path)

    def create_borrower_case(self, borrower_case: BorrowerCase) -> BorrowerCase:
        return self.storage.create_borrower_case(borrower_case)

    def get_borrower_case(self, borrower_id: str) -> BorrowerCase | None:
        return self.storage.get_borrower_case(borrower_id)

    def list_borrower_cases(self) -> list[BorrowerCase]:
        return self.storage.list_borrower_cases()

    def update_borrower_case(self, borrower_id: str, borrower_case: BorrowerCase) -> BorrowerCase:
        return self.storage.update_borrower_case(borrower_id, borrower_case)

    def delete_borrower_case(self, borrower_id: str) -> bool:
        return self.storage.delete_borrower_case(borrower_id)
