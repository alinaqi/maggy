"""Shared options and loading for the harness commands."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum
from pathlib import Path

import typer

from maggy.harness.cli.env import ToolEnv
from maggy.harness.emitters import Scope
from maggy.harness.errors import HarnessConfigError
from maggy.harness.loader import ResolvedProfile, resolve_profile


class ScopeKind(str, Enum):
    user = "user"
    project = "project"


class AgentName(str, Enum):
    claude = "claude"
    codex = "codex"
    opencode = "opencode"
    pi = "pi"


REPO = typer.Option(None, "--repo", help="Repository root (default: current directory).")
SCOPE = typer.Option(ScopeKind.user, "--scope", help="user: write into HOME; project: into --repo.")
AGENT = typer.Option(None, "--agent", "-a", help="Limit to this agent (repeatable).")


@contextmanager
def config_errors() -> Iterator[None]:
    """A broken profile is an error (exit 1) with file and key, not a traceback."""
    try:
        yield
    except HarnessConfigError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(1) from exc


def load(env: ToolEnv, repo: Path | None) -> ResolvedProfile:
    return resolve_profile(repo_root=repo, personal_path=env.state_dir / "harness.yaml")


def make_scope(env: ToolEnv, kind: ScopeKind, repo: Path | None) -> Scope:
    root = env.home if kind is ScopeKind.user else (repo or Path.cwd())
    return Scope(kind=kind.value, root=root.resolve(), home=env.home)


def selected_agents(resolved: ResolvedProfile, agents: list[AgentName] | None) -> list[str]:
    """--agent values, else the profile's installed agents, else every agent."""
    if agents:
        return [agent.value for agent in agents]
    return list(resolved.profile.agents.installed) or [agent.value for agent in AgentName]
