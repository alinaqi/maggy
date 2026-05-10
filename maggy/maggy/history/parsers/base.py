"""Abstract base for CLI history parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from maggy.history.models import SessionEntry


class HistoryParser(ABC):
    """Base protocol for CLI history parsers."""

    provider: str

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this CLI's data directory exists."""
        ...

    @abstractmethod
    def parse_sessions(
        self, limit: int = 500,
    ) -> list[SessionEntry]:
        """Parse session history into SessionEntry list."""
        ...

    @abstractmethod
    def session_count(self) -> int:
        """Return total number of sessions available."""
        ...
