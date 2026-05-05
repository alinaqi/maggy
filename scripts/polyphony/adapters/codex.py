"""Codex CLI adapter (§8.2).

Builds CLI command: codex exec --full-auto <prompt>
Parses NDJSON events for completion/quota detection.
"""

from __future__ import annotations

from ..models import AgentProfile, RunSpec


class CodexAdapter:
    """Adapter for OpenAI Codex CLI."""

    def build_command(
        self,
        profile: AgentProfile,
        run_spec: RunSpec,
    ) -> list[str]:
        """Build codex CLI command list."""
        parts = profile.cli_command.split()
        if "--full-auto" not in parts:
            parts.append("--full-auto")
        return parts

    def detect_completion(self, event: dict) -> bool:
        """Check if event signals task completion."""
        return event.get("status") == "completed"

    def detect_quota(self, text: str) -> bool:
        """Check if output indicates quota/rate limit."""
        lower = text.lower()
        return "quota" in lower or "rate limit" in lower
