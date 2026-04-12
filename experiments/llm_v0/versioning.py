from __future__ import annotations

from experiments.llm_v0.defaults import DEFAULT_EVALUATOR_TEXT, DEFAULT_PROMPT_TEXT
from experiments.llm_v0.models import ExperimentState, LinkedVersion, VersionAuditEvent
from experiments.llm_v0.store import JsonStore, utc_now


class LinkedVersionManager:
    def __init__(self, store: JsonStore, kind: str, initial_text: str) -> None:
        self.store = store
        self.kind = kind
        self.initial_text = initial_text

    def bootstrap(self) -> LinkedVersion:
        self.store.bootstrap()
        versions = self.store.load_all_versions(self.kind)
        state = self.store.load_state()

        if not versions:
            version = LinkedVersion(
                version_id=f"{self.kind}_v1",
                kind=self.kind,
                text=self.initial_text,
                created_at=utc_now(),
            )
            self.store.save_version(version)
            self._set_active_state(state, version.version_id)
            self._set_next_counter(state, 2)
            self.store.save_state(state)
            self.store.append_history(
                VersionAuditEvent(
                    event_type="INIT",
                    version_kind=self.kind,
                    version_id=version.version_id,
                    created_at=utc_now(),
                )
            )
            return version

        highest_number = max(int(version.version_id.split("_v")[1]) for version in versions)
        self._set_next_counter(state, max(self._get_next_counter(state), highest_number + 1))
        if not self._has_history():
            chain = self.list_chain()
            root = chain[0] if chain else min(versions, key=lambda item: int(item.version_id.split("_v")[1]))
            self.store.append_history(
                VersionAuditEvent(
                    event_type="INIT",
                    version_kind=self.kind,
                    version_id=root.version_id,
                    created_at=utc_now(),
                )
            )
        active_version = self._get_active_version_id(state)
        if not any(version.version_id == active_version for version in versions):
            chain = self.list_chain()
            fallback = chain[-1].version_id if chain else versions[0].version_id
            self._set_active_state(state, fallback)
        self.store.save_state(state)
        return self.get_active()

    def get(self, version_id: str) -> LinkedVersion:
        return self.store.load_version(self.kind, version_id)

    def get_active(self) -> LinkedVersion:
        state = self.store.load_state()
        return self.get(self._get_active_version_id(state))

    def list_chain(self) -> list[LinkedVersion]:
        versions = {version.version_id: version for version in self.store.load_all_versions(self.kind)}
        if not versions:
            return []

        roots = [version for version in versions.values() if version.previous_version_id is None]
        if not roots:
            return sorted(versions.values(), key=lambda item: int(item.version_id.split("_v")[1]))

        current = min(roots, key=lambda item: int(item.version_id.split("_v")[1]))
        chain = [current]
        while current.next_version_id:
            next_version = versions.get(current.next_version_id)
            if next_version is None:
                break
            chain.append(next_version)
            current = next_version
        return chain

    def create_candidate(self, text: str, diff: str, parent_version_id: str) -> LinkedVersion:
        version = LinkedVersion(
            version_id=self.store.reserve_next_version_id(self.kind),
            kind=self.kind,
            text=text,
            diff=diff,
            previous_version_id=parent_version_id,
            created_at=utc_now(),
        )
        self.store.save_version(version)
        self.store.append_history(
            VersionAuditEvent(
                event_type="CREATE_CANDIDATE",
                version_kind=self.kind,
                version_id=version.version_id,
                created_at=utc_now(),
                details={"parent_version_id": parent_version_id},
            )
        )
        return version

    def adopt_candidate(self, version_id: str) -> LinkedVersion:
        version = self.get(version_id)
        if version.previous_version_id:
            parent = self.get(version.previous_version_id)
            parent.next_version_id = version.version_id
            self.store.save_version(parent)

        state = self.store.load_state()
        self._set_active_state(state, version.version_id)
        self.store.save_state(state)
        self.store.append_history(
            VersionAuditEvent(
                event_type="ADOPT",
                version_kind=self.kind,
                version_id=version.version_id,
                created_at=utc_now(),
                details={"parent_version_id": version.previous_version_id},
            )
        )
        return version

    def reject_candidate(self, version_id: str, reason: str | None = None) -> None:
        self.store.delete_version(self.kind, version_id)
        self.store.append_history(
            VersionAuditEvent(
                event_type="REJECT",
                version_kind=self.kind,
                version_id=version_id,
                created_at=utc_now(),
                details={"reason": reason or ""},
            )
        )

    def revert_to(self, version_id: str | None = None) -> LinkedVersion:
        active = self.get_active()
        if version_id is None:
            if not active.previous_version_id:
                raise ValueError(f"Cannot revert {self.kind}_v1")
            version_id = active.previous_version_id

        chain = self.list_chain()
        chain_ids = [version.version_id for version in chain]
        if version_id not in chain_ids:
            raise ValueError(f"Unknown {self.kind} chain version: {version_id}")

        target = self.get(version_id)
        if target.version_id == active.version_id:
            return target

        removed_ids: list[str] = []
        current_id = target.next_version_id
        while current_id:
            current = self.get(current_id)
            removed_ids.append(current.version_id)
            next_id = current.next_version_id
            self.store.delete_version(self.kind, current.version_id)
            current_id = next_id

        target.next_version_id = None
        self.store.save_version(target)

        state = self.store.load_state()
        self._set_active_state(state, target.version_id)
        self.store.save_state(state)
        self.store.append_history(
            VersionAuditEvent(
                event_type="REVERT",
                version_kind=self.kind,
                version_id=target.version_id,
                created_at=utc_now(),
                details={"removed_version_ids": removed_ids},
            )
        )
        return target

    def _get_active_version_id(self, state: ExperimentState) -> str:
        return state.active_prompt_version if self.kind == "prompt" else state.active_evaluator_version

    def _set_active_state(self, state: ExperimentState, version_id: str) -> None:
        if self.kind == "prompt":
            state.active_prompt_version = version_id
        else:
            state.active_evaluator_version = version_id

    def _get_next_counter(self, state: ExperimentState) -> int:
        return state.next_prompt_number if self.kind == "prompt" else state.next_evaluator_number

    def _set_next_counter(self, state: ExperimentState, value: int) -> None:
        if self.kind == "prompt":
            state.next_prompt_number = value
        else:
            state.next_evaluator_number = value

    def _has_history(self) -> bool:
        history_path = self.store.history_dir / f"{self.kind}_history.jsonl"
        return history_path.exists() and history_path.stat().st_size > 0


class PromptVersionManager(LinkedVersionManager):
    def __init__(self, store: JsonStore) -> None:
        super().__init__(store=store, kind="prompt", initial_text=DEFAULT_PROMPT_TEXT)


class EvaluatorVersionManager(LinkedVersionManager):
    def __init__(self, store: JsonStore) -> None:
        super().__init__(store=store, kind="evaluator", initial_text=DEFAULT_EVALUATOR_TEXT)


class Loop1ChangeManager(PromptVersionManager):
    pass


class Loop2ChangeManager(EvaluatorVersionManager):
    pass
