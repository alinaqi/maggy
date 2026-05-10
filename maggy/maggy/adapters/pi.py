"""PiAdapter — unified agent harness wrapping CLI adapters.

Provides a single interface for sending prompts to any model,
streaming events, detecting quota/failures, and triggering
fallback to the next model in the tier chain.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class ModelEntry:
    """A registered model with provider and cost info."""

    name: str
    provider: str
    model_id: str
    tier: str  # cheap | medium | premium | validator
    cost_per_1k: float = 0.0
    daily_limit_usd: float = 50.0
    cli_command: str = "claude"
    context_window: int = 200_000


DEFAULT_MODELS: list[ModelEntry] = [
    ModelEntry("kimi", "moonshot", "kimi-k2", "cheap",
               0.001, 10.0, "kimi", 128_000),
    ModelEntry("deepseek", "deepseek", "deepseek-v3", "cheap",
               0.002, 10.0, "deepseek", 128_000),
    ModelEntry("gpt", "openai", "gpt-4o", "medium",
               0.01, 20.0, "codex", 128_000),
    ModelEntry("claude", "anthropic", "claude-sonnet-4",
               "premium", 0.03, 50.0, "claude", 200_000),
    ModelEntry("codex", "openai", "codex", "validator",
               0.02, 30.0, "codex", 200_000),
]

QUOTA_MARKERS = frozenset({
    "rate limit", "quota", "429", "too many requests",
    "capacity", "overloaded",
})


@dataclass
class RunResult:
    """Outcome of a single model run."""

    model: str
    success: bool
    output: str = ""
    error: str = ""
    cost_usd: float = 0.0
    turns: int = 0
    quota_hit: bool = False


class PiAdapter:
    """Unified adapter that wraps CLI model invocations."""

    def __init__(
        self,
        models: list[ModelEntry] | None = None,
    ):
        self._models = {
            m.name: m for m in (models or DEFAULT_MODELS)
        }
        self._fallback_order = [
            m.name for m in sorted(
                (models or DEFAULT_MODELS),
                key=lambda m: m.cost_per_1k,
            )
        ]

    def get_model(self, name: str) -> ModelEntry | None:
        return self._models.get(name)

    def list_models(self) -> list[ModelEntry]:
        return list(self._models.values())

    def fallback_chain(self, start: str) -> list[str]:
        """Return models to try after start, ordered by cost."""
        try:
            idx = self._fallback_order.index(start)
        except ValueError:
            return self._fallback_order
        return self._fallback_order[idx + 1:]

    async def send_prompt(
        self,
        model_name: str,
        prompt: str,
        working_dir: str,
        max_turns: int = 20,
        timeout: int = 600,
    ) -> RunResult:
        """Send prompt to model CLI. Returns RunResult."""
        model = self._models.get(model_name)
        if not model:
            return RunResult(
                model=model_name, success=False,
                error=f"Unknown model: {model_name}",
            )

        cmd = self._build_command(model, prompt, max_turns)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=working_dir,
            )
            stdout, _ = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
            text = (stdout or b"").decode("utf-8", errors="replace")
            quota = self._detect_quota(text)

            if proc.returncode != 0:
                return RunResult(
                    model=model_name, success=False,
                    output=text, error=f"Exit code {proc.returncode}",
                    quota_hit=quota,
                )
            return RunResult(
                model=model_name, success=True,
                output=text, quota_hit=quota,
            )
        except asyncio.TimeoutError:
            return RunResult(
                model=model_name, success=False,
                error="Timed out",
            )
        except FileNotFoundError:
            return RunResult(
                model=model_name, success=False,
                error=f"CLI '{model.cli_command}' not found",
            )

    async def send_with_fallback(
        self,
        model_name: str,
        prompt: str,
        working_dir: str,
        max_turns: int = 20,
    ) -> RunResult:
        """Try model, fall back on quota/failure."""
        result = await self.send_prompt(
            model_name, prompt, working_dir, max_turns,
        )
        if result.success:
            return result

        chain = self.fallback_chain(model_name)
        for fallback in chain:
            logger.info(
                "Falling back from %s to %s",
                model_name, fallback,
            )
            result = await self.send_prompt(
                fallback, prompt, working_dir, max_turns,
            )
            if result.success:
                return result

        return result

    def _build_command(
        self, model: ModelEntry, prompt: str, max_turns: int,
    ) -> list[str]:
        """Build CLI command for model."""
        cmd = [model.cli_command, "-p", prompt]
        if model.cli_command == "claude":
            cmd += [
                "--output-format", "text",
                "--max-turns", str(max_turns),
                "--dangerously-skip-permissions",
            ]
        return cmd

    def _detect_quota(self, text: str) -> bool:
        """Check if output indicates quota/rate limit."""
        lower = text.lower()
        return any(m in lower for m in QUOTA_MARKERS)
