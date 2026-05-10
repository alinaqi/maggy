"""Typed memory categories for Mesh sharing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class MemoryType(str, Enum):
    SCORE = "score"
    PATTERN = "pattern"
    POLICY = "policy"
    GAP = "gap"


@dataclass
class SharedMemory:
    """A unit of shared memory in the Mesh."""

    key: str
    memory_type: str
    content: dict = field(default_factory=dict)
    source_peer: str = ""
    confidence: float = 1.0
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    @property
    def is_trusted(self) -> bool:
        return self.confidence >= 0.5
