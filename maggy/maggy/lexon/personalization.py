"""Implicit learning — tracks 5 user behavior signals."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class UserSignals:
    """Five implicit signals for personalization."""

    tool_frequency: Counter = field(
        default_factory=Counter
    )
    correction_pairs: list[tuple[str, str]] = field(
        default_factory=list
    )
    preferred_aliases: dict[str, str] = field(
        default_factory=dict
    )
    rejection_count: Counter = field(
        default_factory=Counter
    )
    confirmation_rate: dict[str, float] = field(
        default_factory=dict
    )


class PersonalizationEngine:
    """Learns from user behavior to improve intent parsing."""

    def __init__(self):
        self._signals = UserSignals()

    def record_use(self, tool: str) -> None:
        """Signal 1: Track tool usage frequency."""
        self._signals.tool_frequency[tool] += 1

    def record_correction(
        self, wrong: str, correct: str,
    ) -> None:
        """Signal 2: Track user corrections."""
        self._signals.correction_pairs.append(
            (wrong, correct)
        )

    def record_alias(
        self, phrase: str, tool: str,
    ) -> None:
        """Signal 3: Track preferred naming."""
        self._signals.preferred_aliases[
            phrase.lower()
        ] = tool

    def record_rejection(self, tool: str) -> None:
        """Signal 4: Track rejected suggestions."""
        self._signals.rejection_count[tool] += 1

    def get_preferred(self, phrase: str) -> str | None:
        """Check if user has a preference for this phrase."""
        return self._signals.preferred_aliases.get(
            phrase.lower()
        )

    def top_tools(self, n: int = 5) -> list[str]:
        """Return most frequently used tools."""
        return [
            t for t, _ in self._signals.tool_frequency.most_common(n)
        ]

    @property
    def signals(self) -> UserSignals:
        return self._signals
