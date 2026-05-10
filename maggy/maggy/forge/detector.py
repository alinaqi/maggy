"""Capability gap detection — monitors unresolvable requests.

Tracks patterns of failed tool lookups and triggers Forge
after repeated occurrences of the same gap.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

TRIGGER_THRESHOLD = 3


@dataclass
class GapRecord:
    """A detected capability gap."""

    capability: str
    occurrences: int = 0
    triggered: bool = False


class GapDetector:
    """Monitors capability gaps across requests."""

    def __init__(self, threshold: int = TRIGGER_THRESHOLD):
        self._gaps: Counter = Counter()
        self._threshold = threshold
        self._triggered: set[str] = set()

    def record_gap(self, capability: str) -> bool:
        """Record a gap. Returns True if threshold reached."""
        key = capability.lower().strip()
        self._gaps[key] += 1
        if (
            self._gaps[key] >= self._threshold
            and key not in self._triggered
        ):
            self._triggered.add(key)
            return True
        return False

    def list_gaps(self) -> list[GapRecord]:
        """Return all recorded gaps."""
        return [
            GapRecord(
                capability=cap,
                occurrences=count,
                triggered=cap in self._triggered,
            )
            for cap, count in self._gaps.most_common()
        ]

    def top_gaps(self, n: int = 5) -> list[GapRecord]:
        """Return top N gaps by occurrence count."""
        return self.list_gaps()[:n]

    def reset(self, capability: str) -> None:
        """Reset a gap counter after resolution."""
        key = capability.lower().strip()
        if key in self._gaps:
            del self._gaps[key]
        self._triggered.discard(key)
