from __future__ import annotations

import os

from experiments.llm_v0.models import LogEntry
from experiments.llm_v0.store import JsonStore, utc_now


class LogCollector:
    def __init__(self, store: JsonStore) -> None:
        self.store = store

    def collect(
        self,
        source: str,
        message: str,
        metadata: dict | None = None,
        caller_cwd: str | None = None,
    ) -> LogEntry:
        entry = LogEntry(
            sequence=self.store.reserve_next_log_sequence(),
            created_at=utc_now(),
            source=source,
            caller_cwd=caller_cwd or os.getcwd(),
            message=message,
            metadata=metadata or {},
        )
        self.store.append_log(entry)
        return entry
