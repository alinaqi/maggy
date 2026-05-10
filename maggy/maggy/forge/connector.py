"""Bridge to mcp-forge — wraps registry, pipeline, codegen.

Connects Maggy to the MCP Forge at ~/Documents/protaige/mcp-forge/
without requiring it on PYTHONPATH. Uses subprocess for pipeline
invocation and file-based data exchange.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from .detector import GapDetector
from .registry import ForgeRegistry

logger = logging.getLogger(__name__)

DEFAULT_FORGE_PATH = Path.home() / "Documents" / "protaige" / "mcp-forge"


@dataclass
class ForgeStatus:
    """Current state of the Forge connector."""

    available: bool
    forge_path: str
    registry_count: int
    pending_gaps: int


class ForgeConnector:
    """Bridge between Maggy and MCP Forge."""

    def __init__(
        self, forge_path: Path | None = None,
    ):
        self._path = forge_path or DEFAULT_FORGE_PATH
        self._available = self._path.exists()
        self.registry = ForgeRegistry(
            self._path if self._available else None,
        )
        self.detector = GapDetector()

    @property
    def available(self) -> bool:
        return self._available

    def status(self) -> ForgeStatus:
        """Return current connector status."""
        return ForgeStatus(
            available=self._available,
            forge_path=str(self._path),
            registry_count=self.registry.count,
            pending_gaps=len(self.detector.list_gaps()),
        )

    def search_tools(self, query: str) -> list[dict]:
        """Search the Forge registry."""
        results = self.registry.search(query)
        return [
            {
                "slug": t.slug,
                "mcp_url": t.mcp_url,
                "has_mcp": t.has_mcp,
                "auth_method": t.auth_method,
            }
            for t in results
        ]

    def report_gap(self, capability: str) -> dict:
        """Report a capability gap. Returns trigger status."""
        triggered = self.detector.record_gap(capability)
        return {
            "capability": capability,
            "triggered": triggered,
            "message": (
                f"Forge triggered for '{capability}'"
                if triggered
                else f"Gap recorded ({capability})"
            ),
        }

    def get_gaps(self) -> list[dict]:
        """Return all detected gaps."""
        return [
            {
                "capability": g.capability,
                "occurrences": g.occurrences,
                "triggered": g.triggered,
            }
            for g in self.detector.top_gaps(10)
        ]
