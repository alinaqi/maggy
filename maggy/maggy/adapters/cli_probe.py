"""Subprocess probes for CLI discovery: --help, --version, ollama models."""

from __future__ import annotations

import logging
import os
import subprocess

logger = logging.getLogger(__name__)

HELP_TIMEOUT = 10
DEFAULT_OLLAMA_MODEL = "qwen3-coder:30b-a3b-q8_0"
# Prefer Qwen3-Coder (MoE, 3.3B active), then older coding models.
_OLLAMA_PREFS = [
    DEFAULT_OLLAMA_MODEL, "qwen3-coder:30b",
    "qwen2.5-coder:32b", "qwen2.5-coder:14b",
    "qwen2.5-coder:7b", "deepseek-coder-v2",
    "codellama:34b", "codellama:13b",
    "qwen3:32b", "llama3.1:70b", "llama3.1:8b",
]


def clean_env() -> dict[str, str]:
    """Return env without CLAUDECODE to avoid nesting block."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    return env


def _run(cmd: list[str]) -> str | None:
    """Run a probe command; return stdout+stderr, or None on failure."""
    try:
        out = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=HELP_TIMEOUT, env=clean_env(),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.debug("Probe failed for %s: %s", cmd, exc)
        return None
    return out.stdout + out.stderr


def get_help(binary: str, subcommand: str) -> str:
    """Run `<binary> [subcommand] --help` and return its output."""
    cmd = [binary, subcommand, "--help"] if subcommand else [binary, "--help"]
    return (_run(cmd) or "").strip()


def get_version(binary: str) -> str:
    """Get the first line of the CLI's version output."""
    for flag in ("--version", "-V", "-v"):
        text = (_run([binary, flag]) or "").strip()
        if text and len(text) < 200:
            return text.split("\n")[0]
    return ""


def detect_ollama_model(binary: str) -> str:
    """Find the best coding model available in ollama."""
    listing = _run([binary, "list"])
    if listing is None:
        return DEFAULT_OLLAMA_MODEL
    lowered = listing.lower()
    for model in _OLLAMA_PREFS:
        if model.split(":")[0] in lowered:
            return model
    lines = listing.strip().splitlines()
    return lines[1].split()[0] if len(lines) > 1 else DEFAULT_OLLAMA_MODEL
