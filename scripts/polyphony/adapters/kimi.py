"""Kimi CLI adapter (§8.3).

Builds CLI command: kimi --print -y <prompt>
Stub until Kimi headless mode stabilizes.
"""

from __future__ import annotations

from ..models import AgentProfile, RunSpec


class KimiAdapter:
    """Adapter for Moonshot Kimi CLI."""

    def build_command(
        self,
        profile: AgentProfile,
        run_spec: RunSpec,
    ) -> list[str]:
        """Build kimi CLI command list."""
        parts = profile.cli_command.split()
        return parts

    def detect_completion(self, event: dict) -> bool:
        """Check if event signals task completion."""
        return event.get("done") is True

    def detect_quota(self, text: str) -> bool:
        """Check if output indicates quota/rate limit."""
        lower = text.lower()
        return "rate limit" in lower or "quota" in lower
