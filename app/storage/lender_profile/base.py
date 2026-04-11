from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.lender_profile import LenderProfile


class LenderProfileStorage(ABC):
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
