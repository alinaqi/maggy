"""LexonRecord — parsed intent with confidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class LexonRecord:
    """A parsed user intent."""

    phrase: str
    resolved_tool: str = ""
    confidence: float = 0.0
    candidates: list[str] = field(default_factory=list)
    disambiguation_mode: str = ""  # "" | self_clarify | user_clarify
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )

    @property
    def is_ambiguous(self) -> bool:
        return self.confidence < 0.7

    @property
    def needs_user_input(self) -> bool:
        return self.disambiguation_mode == "user_clarify"
