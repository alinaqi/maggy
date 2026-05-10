"""Multi-path retrieval for Engram records."""

from __future__ import annotations

from .record import EngramRecord
from .store import EngramStore


class EngramRetrieval:
    """Multi-path retrieval: semantic, temporal, causal, entity."""

    def __init__(self, store: EngramStore):
        self._store = store

    def by_namespace(
        self, namespace: str, limit: int = 50,
    ) -> list[EngramRecord]:
        """Retrieve by namespace (project/session scope)."""
        return self._store.query(
            namespace=namespace, limit=limit,
        )

    def by_type(
        self, memory_type: str, limit: int = 50,
    ) -> list[EngramRecord]:
        """Retrieve by memory type (fact/decision/etc)."""
        return self._store.query(
            memory_type=memory_type, limit=limit,
        )

    def by_keyword(
        self, keyword: str, namespace: str | None = None,
        limit: int = 50,
    ) -> list[EngramRecord]:
        """Simple keyword search in content."""
        records = self._store.query(
            namespace=namespace, limit=1000,
        )
        matched = [
            r for r in records
            if keyword.lower() in r.content.lower()
        ]
        return matched[:limit]

    def by_tag(
        self, tag: str, namespace: str | None = None,
        limit: int = 50,
    ) -> list[EngramRecord]:
        """Retrieve by tag."""
        records = self._store.query(
            namespace=namespace, limit=1000,
        )
        matched = [
            r for r in records if tag in r.tags
        ]
        return matched[:limit]

    def recent(self, limit: int = 20) -> list[EngramRecord]:
        """Retrieve most recent records across all namespaces."""
        return self._store.query(
            active_only=True, limit=limit,
        )
