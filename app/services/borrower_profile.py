from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.borrower_profile import BorrowerProfile
from app.storage.borrower_profile.base import BorrowerProfileStorage
from app.storage.borrower_profile.json_file import JsonFileBorrowerProfileStorage


class BorrowerProfileService(ABC):
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


class FileBorrowerProfileService(BorrowerProfileService):
    def __init__(self, file_path: str = "data/app/borrower_profiles.json") -> None:
        self.storage: BorrowerProfileStorage = JsonFileBorrowerProfileStorage(file_path)

    def create_borrower_profile(self, borrower_profile: BorrowerProfile) -> BorrowerProfile:
        return self.storage.create_borrower_profile(borrower_profile)

    def get_borrower_profile(self, borrower_id: str) -> BorrowerProfile | None:
        return self.storage.get_borrower_profile(borrower_id)

    def list_borrower_profiles(self) -> list[BorrowerProfile]:
        return self.storage.list_borrower_profiles()

    def update_borrower_profile(self, borrower_id: str, borrower_profile: BorrowerProfile) -> BorrowerProfile:
        return self.storage.update_borrower_profile(borrower_id, borrower_profile)

    def delete_borrower_profile(self, borrower_id: str) -> bool:
        return self.storage.delete_borrower_profile(borrower_id)
