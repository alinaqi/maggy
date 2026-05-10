"""Quarantine system for untrusted mesh data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class QuarantineEntry:
    """A quarantined memory item."""

    key: str
    source_peer: str
    reason: str
    content: dict = field(default_factory=dict)
    memory_type: str = ""
    quarantined_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


class QuarantineStore:
    """Manages quarantined data from mesh peers."""

    def __init__(self, store=None, org: str = ""):
        self._entries: dict[str, QuarantineEntry] = {}
        self._store = store
        self._org = org
        if store and org:
            self._load_from_store()

    def _load_from_store(self) -> None:
        for row in self._store.list_quarantined(self._org):
            self._entries[row["key"]] = QuarantineEntry(
                key=row["key"],
                source_peer=row["source_peer"],
                reason=row["reason"],
                content=row.get("content", {}),
                memory_type=row.get("memory_type", ""),
            )

    def quarantine(
        self, key: str, source: str,
        reason: str, content: dict,
        memory_type: str = "",
    ) -> QuarantineEntry:
        entry = QuarantineEntry(
            key=key, source_peer=source,
            reason=reason, content=content,
            memory_type=memory_type,
        )
        self._entries[key] = entry
        if self._store and self._org:
            self._store.quarantine_item(
                self._org, key, source, reason, content,
            )
        return entry

    def get(self, key: str) -> QuarantineEntry | None:
        return self._entries.get(key)

    def list_all(self) -> list[QuarantineEntry]:
        return list(self._entries.values())

    def promote(self, key: str) -> QuarantineEntry | None:
        """Remove from quarantine and return entry for acceptance."""
        entry = self._entries.pop(key, None)
        if self._store and self._org:
            self._store.promote_item(self._org, key)
        return entry

    def reject(self, key: str) -> bool:
        """Permanently reject quarantined item."""
        if key in self._entries:
            del self._entries[key]
        if self._store and self._org:
            self._store.promote_item(self._org, key)
            return True
        return key is not None

    @property
    def count(self) -> int:
        return len(self._entries)
