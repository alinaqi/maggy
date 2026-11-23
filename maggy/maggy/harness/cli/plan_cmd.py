"""`maggy harness diff` and `maggy harness apply`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer

from maggy.harness.apply import apply_changes
from maggy.harness.changes import FileChange
from maggy.harness.cli.command import options_command
from maggy.harness.cli.env import get_env
from maggy.harness.cli.options import (
    AGENT, REPO, SCOPE, AgentName, ScopeKind, config_errors, load, make_scope, selected_agents,
)
from maggy.harness.cli.render import pending, problems, report_lines
from maggy.harness.compile import compile_plan, emitters_for
from maggy.harness.emitters import Scope


@dataclass
class PlanOptions:
    agent: list[AgentName] | None = AGENT
    scope: ScopeKind = SCOPE
    repo: Path | None = REPO


@dataclass
class ApplyOptions(PlanOptions):
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply without asking.")
    take_mine: bool = typer.Option(False, "--take-mine", help="Conflicts: keep the on-disk edits.")
    take_profile: bool = typer.Option(False, "--take-profile", help="Conflicts: write the profile.")


def _plan(ctx: typer.Context, opts: PlanOptions, resolution: str | None = None) -> tuple[Scope, list[FileChange]]:
    env = get_env(ctx)
    project = opts.scope is ScopeKind.project
    repo = (opts.repo or Path.cwd()).resolve() if project else None
    with config_errors():
        resolved = load(env, repo)
        scope = make_scope(env, opts.scope, repo).model_copy(update={"resolution": resolution})
        emitters = emitters_for(selected_agents(resolved, opts.agent), env.sources)
        return scope, compile_plan(resolved.profile, scope, emitters)


def _echo(changes: list[FileChange]) -> None:
    for text in report_lines(changes):
        typer.echo(text)


@options_command(PlanOptions)
def diff(ctx: typer.Context, opts: PlanOptions) -> None:
    """Unified diff of what apply would write; exit 1 when there are conflicts."""
    _, changes = _plan(ctx, opts)
    _echo(changes)
    if not pending(changes) and not problems(changes):
        typer.echo("No changes.")
    if problems(changes):
        raise typer.Exit(1)


def _resolution(opts: ApplyOptions) -> str | None:
    if opts.take_mine and opts.take_profile:
        raise typer.BadParameter("use only one of --take-mine and --take-profile")
    return "take_mine" if opts.take_mine else "take_profile" if opts.take_profile else None


@options_command(ApplyOptions)
def apply(ctx: typer.Context, opts: ApplyOptions) -> None:
    """Plan, show the diff, confirm, back up, write and update harness.lock."""
    resolution = _resolution(opts)
    scope, changes = _plan(ctx, opts, resolution)
    _echo(changes)
    if not pending(changes) and resolution is None:
        typer.echo("Nothing to apply." if not problems(changes) else "Nothing applied.")
        raise typer.Exit(1 if problems(changes) else 0)
    if pending(changes) and not opts.yes and not typer.confirm("Apply these changes?", default=False):
        typer.echo("Not applied.")
        raise typer.Exit(1)
    report = apply_changes([c for c in changes if c.status == "ok"], scope.context())
    _summary(report)
    if problems(changes) or report.skipped:
        raise typer.Exit(1)


def _summary(report) -> None:
    for path in report.written:
        typer.echo(f"wrote {path}")
    for path, reason in report.skipped.items():
        typer.echo(f"skipped {path}: {reason}")
    if report.backup_dir:
        typer.echo(f"backup: {report.backup_dir}")
