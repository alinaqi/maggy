"""`maggy harness init`: detect agents, short interview, profile, AWG tokens."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

import typer
import yaml

from maggy.harness.cli.awg_tokens import ensure_awg
from maggy.harness.cli.command import options_command
from maggy.harness.cli.detect import detect_agents
from maggy.harness.cli.env import ToolEnv, get_env
from maggy.harness.cli.options import config_errors
from maggy.harness.layering import deep_merge
from maggy.harness.loader import read_layer
from maggy.harness.presets import load_preset

STRATEGIES = ["cost", "quality", "speed", "custom"]


@dataclass
class InitOptions:
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept every default; no questions.")
    force: bool = typer.Option(False, "--force", help="Rewrite an existing profile.")
    preset: str | None = typer.Option(None, "--preset", help="Start from a shipped preset (token-economy).")


def _check(options: list[str], value: str) -> str:
    if value.lower() not in options:
        raise typer.BadParameter(f"choose one of: {', '.join(options)}")
    return value.lower()


def _choose(label: str, options: list[str], default: str) -> str:
    """Prompt until the answer is one of options."""
    return typer.prompt(f"{label} ({'/'.join(options)})", default=default,
                        value_proc=partial(_check, options))


def _interview(agents: list[str], yes: bool) -> dict:
    """Profile answers; --yes takes every default."""
    default = agents[0] if agents else None
    if not yes and agents:
        default = _choose("Default agent", agents, default)
    strategy = "cost" if yes else _choose("Model strategy", STRATEGIES, "cost")
    awg = yes or typer.confirm("Track work in AWG?", default=True)
    t3 = not yes and typer.confirm("Do you drive agents from T3 Code?", default=False)
    return {"version": 1, "agents": {"installed": agents, "default": default},
            "surfaces": ["t3"] if t3 else [], "models": {"strategy": strategy},
            "work": {"provider": "awg" if awg else "none"}}


def _write_profile(env: ToolEnv, agents: list[str], opts: InitOptions) -> dict:
    """Write ~/.maggy/harness.yaml unless one exists (and --force is off)."""
    path = env.state_dir / "harness.yaml"
    if path.is_file() and not opts.force:
        typer.echo(f"kept existing profile {path} (use --force to rewrite)")
        return read_layer(path, personal=True)
    with config_errors():
        preset = load_preset(opts.preset) if opts.preset else {}
    data = deep_merge(preset, _interview(agents, opts.yes))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    typer.echo(f"wrote {path}")
    return data


@options_command(InitOptions)
def init(ctx: typer.Context, opts: InitOptions) -> None:
    """Detect agent CLIs, write ~/.maggy/harness.yaml, set up AWG tokens."""
    env = get_env(ctx)
    found = detect_agents(env)
    for agent, version in found.items():
        typer.echo(f"found {agent} {version}")
    data = _write_profile(env, list(found), opts)
    if (data.get("work") or {}).get("provider", "awg") != "awg":
        return
    agents = (data.get("agents") or {}).get("installed") or list(found)
    notes, problems = ensure_awg(env, agents)
    for line in notes + problems:
        typer.echo(line)
    if problems:
        raise typer.Exit(1)
