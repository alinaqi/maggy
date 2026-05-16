"""Gemini CLI adapter — wraps the ~/bin/gemini delegation script.

Supports Gemini 2.5 Flash-Lite, Flash, Pro, and 3.1 Pro Search.
"""

from __future__ import annotations

from ..models import AgentProfile, RunSpec


class GeminiAdapter:
    """Adapter for Google Gemini via delegation script."""

    def build_command(
        self,
        profile: AgentProfile,
        run_spec: RunSpec,
    ) -> list[str]:
        """Build gemini CLI command list."""
        parts = profile.cli_command.split()
        return parts

    def detect_completion(self, event: dict) -> bool:
        """Check if event signals task completion."""
        return event.get("done") is True

    def detect_quota(self, text: str) -> bool:
        """Check if output indicates quota/rate limit."""
        lower = text.lower()
        return "rate limit" in lower or "quota" in lower or "429" in lower
