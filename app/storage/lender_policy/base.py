from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.lender_policy import LenderPolicy


class LenderPolicyStorage(ABC):
    @abstractmethod
    def create_lender_policy(self, lender_policy: LenderPolicy) -> LenderPolicy:
        raise NotImplementedError

    @abstractmethod
    def get_lender_policy(self, lender_id: str) -> LenderPolicy | None:
        raise NotImplementedError

    @abstractmethod
    def list_lender_policies(self) -> list[LenderPolicy]:
        raise NotImplementedError

    @abstractmethod
    def update_lender_policy(self, lender_id: str, lender_policy: LenderPolicy) -> LenderPolicy:
        raise NotImplementedError

    @abstractmethod
    def delete_lender_policy(self, lender_id: str) -> bool:
        raise NotImplementedError
