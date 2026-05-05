"""Claude Code adapter (§8.1).

Builds CLI command: claude -p <prompt> --output-format stream-json
Parses stream-json events for completion/quota detection.
"""

from __future__ import annotations

from ..models import AgentProfile, RunSpec


class ClaudeAdapter:
    """Adapter for Claude Code CLI."""

    def build_command(
        self,
        profile: AgentProfile,
        run_spec: RunSpec,
    ) -> list[str]:
        """Build claude CLI command list."""
        parts = profile.cli_command.split()
        parts += ["--output-format", "stream-json"]
        if run_spec.max_turns:
            parts += ["--max-turns", str(run_spec.max_turns)]
        return parts

    def detect_completion(self, event: dict) -> bool:
        """Check if event signals task completion."""
        return event.get("type") == "result"

    def detect_quota(self, text: str) -> bool:
        """Check if output indicates quota/rate limit."""
        lower = text.lower()
        return "rate limit" in lower or "quota" in lower
