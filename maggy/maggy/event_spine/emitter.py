"""Event emitter — write, query, and trace events."""

from __future__ import annotations

import logging
from dataclasses import asdict

from .header import EventHeader
from .store import EventStore

logger = logging.getLogger(__name__)


class EventEmitter:
    """Thread-safe event emission and query API."""

    def __init__(self, store: EventStore):
        self._store = store

    def emit(self, event: object) -> str:
        """Write event to store. Returns event_id."""
        header = getattr(event, "header", None)
        if not isinstance(header, EventHeader):
            raise ValueError("Event must have an EventHeader")

        data = asdict(event)
        self._store.write(header, data)
        logger.debug(
            "Event %s emitted: %s",
            header.event_type, header.event_id,
        )
        return header.event_id

    def query(
        self,
        task_id: str | None = None,
        event_type: str | None = None,
        project_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query events with optional filters."""
        return self._store.query(
            task_id=task_id,
            event_type=event_type,
            project_id=project_id,
            limit=limit,
        )

    def trace(self, task_id: str) -> list[dict]:
        """Return full ordered event chain for a task."""
        return self._store.query(
            task_id=task_id, limit=10000,
        )

    def count(
        self,
        event_type: str | None = None,
        project_id: str | None = None,
    ) -> int:
        """Count events matching filters."""
        return self._store.count(
            event_type=event_type,
            project_id=project_id,
        )
