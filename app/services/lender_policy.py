from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.lender_policy import LenderPolicy
from app.storage.lender_policy.base import LenderPolicyStorage
from app.storage.lender_policy.json_file import JsonFileLenderPolicyStorage


class LenderPolicyService(ABC):
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


class FileLenderPolicyService(LenderPolicyService):
    def __init__(self, file_path: str = "data/app/lender_policies.json") -> None:
        self.storage: LenderPolicyStorage = JsonFileLenderPolicyStorage(file_path)

    def create_lender_policy(self, lender_policy: LenderPolicy) -> LenderPolicy:
        return self.storage.create_lender_policy(lender_policy)

    def get_lender_policy(self, lender_id: str) -> LenderPolicy | None:
        return self.storage.get_lender_policy(lender_id)

    def list_lender_policies(self) -> list[LenderPolicy]:
        return self.storage.list_lender_policies()

    def update_lender_policy(self, lender_id: str, lender_policy: LenderPolicy) -> LenderPolicy:
        return self.storage.update_lender_policy(lender_id, lender_policy)

    def delete_lender_policy(self, lender_id: str) -> bool:
        return self.storage.delete_lender_policy(lender_id)
