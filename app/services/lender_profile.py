from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.lender_profile import LenderProfile
from app.storage.lender_profile.base import LenderProfileStorage
from app.storage.lender_profile.json_file import JsonFileLenderProfileStorage


class LenderProfileService(ABC):
    @abstractmethod
    def create_lender_profile(self, lender_profile: LenderProfile) -> LenderProfile:
        raise NotImplementedError

    @abstractmethod
    def get_lender_profile(self, lender_id: str) -> LenderProfile | None:
        raise NotImplementedError

    @abstractmethod
    def list_lender_profiles(self) -> list[LenderProfile]:
        raise NotImplementedError

    @abstractmethod
    def update_lender_profile(self, lender_id: str, lender_profile: LenderProfile) -> LenderProfile:
        raise NotImplementedError

    @abstractmethod
    def delete_lender_profile(self, lender_id: str) -> bool:
        raise NotImplementedError


class FileLenderProfileService(LenderProfileService):
    def __init__(self, file_path: str = "data/app/lender_profiles.json") -> None:
        self.storage: LenderProfileStorage = JsonFileLenderProfileStorage(file_path)

    def create_lender_profile(self, lender_profile: LenderProfile) -> LenderProfile:
        return self.storage.create_lender_profile(lender_profile)

    def get_lender_profile(self, lender_id: str) -> LenderProfile | None:
        return self.storage.get_lender_profile(lender_id)

    def list_lender_profiles(self) -> list[LenderProfile]:
        return self.storage.list_lender_profiles()

    def update_lender_profile(self, lender_id: str, lender_profile: LenderProfile) -> LenderProfile:
        return self.storage.update_lender_profile(lender_id, lender_profile)

    def delete_lender_profile(self, lender_id: str) -> bool:
        return self.storage.delete_lender_profile(lender_id)
