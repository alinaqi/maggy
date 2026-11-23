"""`maggy harness doctor`: capability table, version drift, tokens, AWG, T3."""

from __future__ import annotations

from pathlib import Path

import typer

from maggy.harness.cli.doctor_checks import (
    awg_checks, capability_gaps, capability_rows, host_execution_warnings,
)
from maggy.harness.cli.env import get_env
from maggy.harness.cli.options import REPO, config_errors, load, selected_agents


def doctor(ctx: typer.Context, repo: Path = REPO) -> None:
    """Per-agent capabilities (native/partial/none) and setup gaps; exit 1 on errors."""
    env = get_env(ctx)
    with config_errors():
        resolved = load(env, repo or Path.cwd())
    agents = selected_agents(resolved, None)
    found = awg_checks(env, resolved.profile, agents)
    found.warnings += host_execution_warnings(resolved.profile)
    for row in capability_rows(env, agents, found):
        typer.echo(row)
    typer.echo("")
    lines = [*capability_gaps(env, agents), *found.info, *(f"WARN {w}" for w in found.warnings), *(f"ERROR {e}" for e in found.errors)]
    for line in lines:
        typer.echo(line)
    if found.errors:
        raise typer.Exit(1)
    typer.echo("doctor: no errors")
