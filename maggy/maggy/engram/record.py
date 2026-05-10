"""EngramRecord — the unit of persistent memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Origin(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    MESH = "mesh"


class Validity(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


@dataclass
class EngramRecord:
    """A single unit of persistent memory."""

    engram_id: str
    namespace: str
    memory_type: str  # fact | decision | code_ref | handoff
    content: str
    origin: str = Origin.EXPLICIT
    validity: str = Validity.ACTIVE
    confidence: float = 1.0
    tags: list[str] = field(default_factory=list)
    source_task: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )
    expires_at: str = ""

    @property
    def is_active(self) -> bool:
        return self.validity == Validity.ACTIVE

    def supersede(self) -> None:
        self.validity = Validity.SUPERSEDED
