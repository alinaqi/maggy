"""Unified adapter for CLI prompts and Pi RPC control.

Auto-discovers installed AI CLIs and their flags at init time
so Maggy can orchestrate any subscription-based tool (claude,
codex, kimi, etc.) without hardcoded command templates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import AsyncIterator

from maggy.adapters.cli_discovery import (
    CliProfile,
    DiscoveryResult,
    discover_all,
)

logger = logging.getLogger(__name__)


def _extract_usage(raw: str) -> tuple[float, int, int, str]:
    """Parse JSON CLI output for cost/tokens; fall back to raw text."""
    try:
        d = json.loads(raw)
        u = d.get("usage") or {}
        return (
            float(d.get("cost_usd") or 0),
            int(u.get("input_tokens") or 0),
            int(u.get("output_tokens") or 0),
            str(d.get("result", raw)),
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        return 0.0, 0, 0, raw


@dataclass
class ModelEntry:
    name: str
    provider: str
    model_id: str
    tier: str
    cost_per_1k: float = 0.0
    daily_limit_usd: float = 50.0
    cli_command: str = "claude"
    context_window: int = 200_000


DELEGATION_BIN = os.path.expanduser("~/bin")

DEFAULT_MODELS: list[ModelEntry] = [
    ModelEntry("local", "ollama", "qwen3-coder:30b-a3b-q8_0", "local", 0.0, 0.0,
               os.path.join(DELEGATION_BIN, "qwen3"), 32_000),
    ModelEntry("gemini-flash-lite", "google", "gemini-2.5-flash-lite", "cheap", 0.0001, 10.0,
               os.path.join(DELEGATION_BIN, "gemini-api"), 1_000_000),
    ModelEntry("deepseek-flash", "deepseek", "deepseek-v4-flash", "cheap", 0.0001, 10.0,
               os.path.join(DELEGATION_BIN, "deepseek"), 128_000),
    ModelEntry("gemini-flash", "google", "gemini-2.5-flash", "medium", 0.0002, 15.0,
               os.path.join(DELEGATION_BIN, "gemini-api"), 1_000_000),
    ModelEntry("deepseek-pro", "deepseek", "deepseek-v4-pro", "medium", 0.0004, 20.0,
               os.path.join(DELEGATION_BIN, "deepseek"), 128_000),
    ModelEntry("kimi", "moonshot", "kimi-k2.6", "cheap", 0.0006, 10.0,
               os.path.join(DELEGATION_BIN, "kimi"), 128_000),
    ModelEntry("grok", "xai", "grok-4.3", "premium", 0.005, 30.0,
               os.path.join(DELEGATION_BIN, "grok"), 128_000),
    ModelEntry("minimax", "minimax", "MiniMax-M2.5", "premium", 0.0005, 30.0,
               os.path.join(DELEGATION_BIN, "minimax"), 200_000),
    ModelEntry("gemini-pro-search", "google", "gemini-3.1-pro", "premium", 0.001, 30.0,
               os.path.join(DELEGATION_BIN, "gemini-api"), 2_000_000),
    ModelEntry("gpt", "openai", "gpt-4o", "medium", 0.01, 20.0, "codex", 128_000),
    ModelEntry("claude", "anthropic", "claude-sonnet-4", "premium", 0.03, 50.0, "claude", 200_000),
    ModelEntry("claude-fable-5", "anthropic", "claude-fable-5", "premium", 0.01, 50.0,
               os.path.join(DELEGATION_BIN, "claude-fable-5"), 1_000_000),
    ModelEntry("codex", "openai", "codex", "validator", 0.02, 30.0, "codex", 200_000),
]

QUOTA_MARKERS = frozenset(
    {"rate limit", "quota", "429", "too many requests", "capacity", "overloaded"}
)

@dataclass
class RunResult:
    model: str
    success: bool
    output: str = ""
    error: str = ""
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    turns: int = 0
    quota_hit: bool = False


class PiAdapter:
    def __init__(
        self,
        models: list[ModelEntry] | None = None,
        rpc_command: str = "pi",
        discovery: DiscoveryResult | None = None,
    ):
        entries = models or DEFAULT_MODELS
        self._models = {entry.name: entry for entry in entries}
        self._fallback_order = [
            entry.name for entry in sorted(entries, key=lambda m: m.cost_per_1k)
        ]
        self._rpc_command = rpc_command
        self._rpc_process: subprocess.Popen[str] | None = None
        self._streaming = False
        self._discovery = discovery or discover_all()
        self._profiles: dict[str, CliProfile] = self._discovery.profiles
        self._log_discovery()

    def get_model(self, name: str) -> ModelEntry | None:
        return self._models.get(name)

    def list_models(self) -> list[ModelEntry]:
        return list(self._models.values())

    def fallback_chain(self, start: str) -> list[str]:
        try:
            idx = self._fallback_order.index(start)
        except ValueError:
            return self._fallback_order
        return self._fallback_order[idx + 1 :]

    async def send_prompt(
        self,
        model_name: str,
        prompt: str,
        working_dir: str,
        max_turns: int = 20,
        timeout: int = 600,
    ) -> RunResult:
        model = self._models.get(model_name)
        if not model:
            return RunResult(model=model_name, success=False, error=f"Unknown model: {model_name}")
        try:
            proc = await self._spawn_prompt(model, prompt, max_turns, working_dir)
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return self._prompt_result(model_name, proc.returncode or 0, stdout or b"")
        except asyncio.TimeoutError:
            return RunResult(model=model_name, success=False, error="Timed out")
        except FileNotFoundError:
            return RunResult(
                model=model_name, success=False, error=f"CLI '{model.cli_command}' not found"
            )

    async def send_with_fallback(
        self,
        model_name: str,
        prompt: str,
        working_dir: str,
        max_turns: int = 20,
    ) -> RunResult:
        result = await self.send_prompt(model_name, prompt, working_dir, max_turns)
        if result.success:
            return result
        for fallback in self.fallback_chain(model_name):
            logger.info("Falling back from %s to %s", model_name, fallback)
            result = await self.send_prompt(fallback, prompt, working_dir, max_turns)
            if result.success:
                return result
        return result

    def send_rpc(self, command: dict[str, object]) -> dict[str, object]:
        proc = self._ensure_rpc_process()
        stdin = self._require_stream(proc.stdin, "stdin")
        stdout = self._require_stream(proc.stdout, "stdout")
        if self._streaming:
            raise RuntimeError("Cannot send RPC while streaming")
        stdin.write(f"{json.dumps(command, separators=(',', ':'))}\n")
        stdin.flush()
        line = stdout.readline()
        return json.loads(line or "{}")

    def switch_model(self, provider: str, model: str) -> bool:
        payload = {"command": "set_model", "provider": provider, "model": model}
        return bool(self.send_rpc(payload).get("ok"))

    async def stream_events(self) -> AsyncIterator[dict[str, object]]:
        if self._streaming:
            raise RuntimeError("Already streaming events")
        stdout = self._require_stream(self._ensure_rpc_process().stdout, "stdout")
        self._streaming = True
        try:
            while True:
                line = await asyncio.to_thread(stdout.readline)
                if not line:
                    break
                yield json.loads(line)
        finally:
            self._streaming = False

    def _build_command(
        self, model: ModelEntry, prompt: str, max_turns: int, wd: str,
    ) -> list[str]:
        profile = self._profiles.get(model.cli_command)
        if profile and profile.installed:
            return profile.build_command(prompt, wd, max_turns)
        # Delegation script conventions (~/bin/)
        if model.name == "gemini-flash-lite":
            return [model.cli_command, "--flash-lite", prompt]
        if model.name == "gemini-flash":
            return [model.cli_command, "--flash", prompt]
        if model.name == "gemini-pro-search":
            return [model.cli_command, "--pro-search", prompt]
        if model.name == "deepseek-flash":
            return [model.cli_command, "--flash", prompt]
        if model.name == "deepseek-pro":
            return [model.cli_command, "--pro", prompt]
        if "/kimi" in model.cli_command:
            return [model.cli_command, "--quiet", "-p", prompt]
        if "/minimax" in model.cli_command or "/claude-fable-5" in model.cli_command:
            return [model.cli_command, prompt]
        # Default: CLI with -p flag
        return [model.cli_command, "-p", prompt]

    def _detect_quota(self, text: str) -> bool:
        return any(marker in text.lower() for marker in QUOTA_MARKERS)

    def _detect_pi(self) -> bool:
        return shutil.which(self._rpc_command) is not None

    async def _spawn_prompt(
        self,
        model: ModelEntry,
        prompt: str,
        max_turns: int,
        working_dir: str,
    ) -> asyncio.subprocess.Process:
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        return await asyncio.create_subprocess_exec(
            *self._build_command(model, prompt, max_turns, working_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=working_dir,
            env=env,
        )

    def _log_discovery(self) -> None:
        for name, p in self._profiles.items():
            level = logging.INFO if p.installed else logging.DEBUG
            logger.log(level, "CLI %s: %s v%s", "OK" if p.installed else "missing", name, p.version)

    @property
    def discovered_profiles(self) -> dict[str, CliProfile]:
        return dict(self._profiles)

    def _prompt_result(self, model_name: str, code: int, stdout: bytes) -> RunResult:
        raw = stdout.decode("utf-8", errors="replace")
        quota = self._detect_quota(raw)
        cost, in_t, out_t, text = _extract_usage(raw)
        return RunResult(
            model=model_name, success=code == 0, output=text,
            error="" if code == 0 else f"Exit code {code}",
            quota_hit=quota, cost_usd=cost,
            input_tokens=in_t, output_tokens=out_t,
        )

    def _ensure_rpc_process(self) -> subprocess.Popen[str]:
        proc = self._rpc_process
        if proc and getattr(proc, "poll", lambda: None)() is None:
            return proc
        self._rpc_process = subprocess.Popen(
            [self._rpc_command], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        return self._rpc_process

    def _require_stream(self, stream: object, name: str):
        if stream is None:
            raise RuntimeError(f"Pi RPC {name} is unavailable")
        return stream
