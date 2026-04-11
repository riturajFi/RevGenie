from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.borrower_profile import BorrowerProfile


class BorrowerProfileStorage(ABC):
    @abstractmethod
    def create_borrower_profile(self, borrower_profile: BorrowerProfile) -> BorrowerProfile:
        raise NotImplementedError

    @abstractmethod
    def get_borrower_profile(self, borrower_id: str) -> BorrowerProfile | None:
        raise NotImplementedError

    @abstractmethod
    def list_borrower_profiles(self) -> list[BorrowerProfile]:
        raise NotImplementedError

    @abstractmethod
    def update_borrower_profile(self, borrower_id: str, borrower_profile: BorrowerProfile) -> BorrowerProfile:
        raise NotImplementedError

    @abstractmethod
    def delete_borrower_profile(self, borrower_id: str) -> bool:
        raise NotImplementedError
