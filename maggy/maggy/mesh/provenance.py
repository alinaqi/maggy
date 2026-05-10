"""Provenance tracking with confidence decay."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

DECAY_PER_HOP = 0.1
MIN_CONFIDENCE = 0.1


@dataclass
class Provenance:
    """Tracks origin and confidence of shared data."""

    origin_peer: str
    hops: int = 0
    base_confidence: float = 1.0
    received_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    @property
    def effective_confidence(self) -> float:
        decayed = self.base_confidence - (self.hops * DECAY_PER_HOP)
        return max(decayed, MIN_CONFIDENCE)

    def add_hop(self) -> Provenance:
        """Create new provenance with one more hop."""
        return Provenance(
            origin_peer=self.origin_peer,
            hops=self.hops + 1,
            base_confidence=self.base_confidence,
        )
