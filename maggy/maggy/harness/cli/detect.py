"""Detect installed agent CLIs and compare them with the tested versions."""

from __future__ import annotations

import re

from maggy.harness.cli.env import ToolEnv
from maggy.harness.compile import AGENTS

# CLI versions each emitter's output format was verified against.
TESTED_VERSIONS = {"claude": "2.1.330", "codex": "0.163.0", "opencode": "1.19.6", "pi": "0.73.1"}
_VERSION = re.compile(r"\d+\.\d+\.\d+")


def agent_version(env: ToolEnv, agent: str) -> str | None:
    """'x.y.z' (or 'unknown') for an agent on PATH; None when not installed."""
    if env.which(agent) is None:
        return None
    done = env.run([agent, "--version"])
    text = (done.stdout or "") + (done.stderr or "")
    found = _VERSION.search(text) if done.returncode == 0 else None
    return found.group(0) if found else "unknown"


def detect_agents(env: ToolEnv) -> dict[str, str]:
    """Installed agents (in AGENTS order) and their versions."""
    found = {agent: agent_version(env, agent) for agent in AGENTS}
    return {agent: version for agent, version in found.items() if version is not None}
