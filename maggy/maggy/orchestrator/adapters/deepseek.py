"""DeepSeek adapter — uses Claude CLI with DeepSeek env overrides.

DeepSeek supports the Anthropic API format, so we invoke the Claude
CLI with ANTHROPIC_BASE_URL pointed at DeepSeek's endpoint.
"""

from __future__ import annotations

import os

from ..models import AgentProfile, RunSpec


class DeepSeekAdapter:
    """Adapter for DeepSeek V4 via Claude CLI."""

    def build_command(
        self,
        profile: AgentProfile,
        run_spec: RunSpec,
    ) -> list[str]:
        """Build claude CLI command with DeepSeek backend."""
        parts = profile.cli_command.split()
        return parts

    def build_env(self) -> dict[str, str]:
        """Env overrides to route Claude CLI to DeepSeek."""
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        return {
            "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
            "ANTHROPIC_AUTH_TOKEN": key,
        }

    def detect_completion(self, event: dict) -> bool:
        """Check if event signals task completion."""
        return event.get("done") is True

    def detect_quota(self, text: str) -> bool:
        """Check if output indicates quota/rate limit."""
        lower = text.lower()
        return "rate limit" in lower or "quota" in lower
