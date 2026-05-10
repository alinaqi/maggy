"""Sync engine — merges shared memories across peers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .memory import SharedMemory
from .quarantine import QuarantineStore

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.5


@dataclass
class SyncResult:
    """Result of a sync operation."""

    accepted: int = 0
    quarantined: int = 0
    rejected: int = 0


class SyncEngine:
    """Merges incoming memories with local store."""

    def __init__(
        self, quarantine: QuarantineStore,
        store=None, org: str = "",
    ):
        self._local: dict[str, SharedMemory] = {}
        self._quarantine = quarantine
        self._store = store
        self._org = org
        if store and org:
            self._load_from_store()

    def _load_from_store(self) -> None:
        for row in self._store.list_memories(self._org):
            self._local[row["key"]] = SharedMemory(
                key=row["key"],
                memory_type=row["memory_type"],
                content=row["content"],
                source_peer=row["source_peer"],
                confidence=row["confidence"],
            )

    def sync_incoming(
        self, memories: list[SharedMemory],
    ) -> SyncResult:
        """Process incoming memories from a peer."""
        result = SyncResult()
        for mem in memories:
            if mem.confidence >= CONFIDENCE_THRESHOLD:
                self._accept(mem)
                result.accepted += 1
            else:
                self._quarantine.quarantine(
                    key=mem.key,
                    source=mem.source_peer,
                    reason="low confidence",
                    content=mem.content,
                    memory_type=mem.memory_type,
                )
                result.quarantined += 1
        return result

    def _accept(self, mem: SharedMemory) -> None:
        self._local[mem.key] = mem
        if self._store and self._org:
            self._store.write_memory(
                self._org, mem.key, mem.memory_type,
                mem.content, mem.source_peer, mem.confidence,
            )

    def promote_from_quarantine(self, key: str) -> bool:
        """Accept a quarantined item into shared memories."""
        entry = self._quarantine.promote(key)
        if not entry:
            return False
        mem = SharedMemory(
            key=entry.key,
            memory_type=entry.memory_type,
            content=entry.content,
            source_peer=entry.source_peer,
            confidence=1.0,
        )
        self._accept(mem)
        return True

    def get_local(self, key: str) -> SharedMemory | None:
        return self._local.get(key)

    def list_local(self) -> list[SharedMemory]:
        return list(self._local.values())

    @property
    def local_count(self) -> int:
        return len(self._local)
