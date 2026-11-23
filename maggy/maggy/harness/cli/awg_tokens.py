"""AWG setup for `harness init`: `awg init` if needed, one agent token per agent.

Secrets go straight from `awg token mint --json` into
~/.maggy/tokens/<agent>.token (mode 0600) and are never printed.
"""

from __future__ import annotations

import json
from pathlib import Path

from maggy.harness.cli.env import ToolEnv
from maggy.harness.fs_safe import atomic_write


def token_path(env: ToolEnv, agent: str) -> Path:
    return env.state_dir / "tokens" / f"{agent}.token"


def _mint(env: ToolEnv, agent: str) -> str | None:
    """Mint and store a token; returns a problem message or None."""
    done = env.run(["awg", "token", "mint", f"maggy-{agent}", "--kind", "agent", "--json"])
    try:
        secret = json.loads(done.stdout)["token"] if done.returncode == 0 else None
    except (ValueError, KeyError, TypeError):
        secret = None
    if not secret:
        return f"{agent}: awg token mint failed (exit {done.returncode})"
    path = token_path(env, agent)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write(path, secret, 0o600)
    return None


def ensure_awg(env: ToolEnv, agents: list[str]) -> tuple[list[str], list[str]]:
    """(notes, problems) after making AWG ready and minting missing tokens."""
    if env.which("awg") is None:
        return ["awg not found on PATH; install AWG, then re-run `maggy harness init`"], []
    notes: list[str] = []
    if env.run(["awg", "status"]).returncode != 0:
        if env.run(["awg", "init"]).returncode != 0:
            return [], ["awg init failed"]
        notes.append("initialised AWG (awg init)")
    missing = [agent for agent in agents if not token_path(env, agent).is_file()]
    problems = [p for p in (_mint(env, agent) for agent in missing) if p]
    minted = [agent for agent in missing if token_path(env, agent).is_file()]
    notes += [f"minted agent token for {agent} -> {token_path(env, agent)}" for agent in minted]
    return notes, problems
