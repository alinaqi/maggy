"""`maggy run`: the AWG runner loop, plus `stop`, `pause` and `resume` (RFC §2.4, §2.6.8)."""

from __future__ import annotations

from pathlib import Path

import typer

from maggy.harness.cli.command import options_command
from maggy.harness.errors import HarnessConfigError
from maggy.runner.awg_errors import AwgError
from maggy.runner.cli_setup import STATE_HELP, RunCliOptions, awg_binary, build_runner, state_of
from maggy.runner.control import request_stop, set_paused
from maggy.runner.intake import IntakeOptions, run_sync, summary, sync_argv
from maggy.worker.git_ops import GitError
from maggy.worker.launch import Refused

app = typer.Typer(help="Run AWG work items through a worker (claim, checks, evidence, submit).",
                  invoke_without_command=True)
_STATE = typer.Option(None, "--state-dir", help=STATE_HELP)
_PROJECT = typer.Option(..., "--project", help="Project key to pause or resume.")


@app.callback()
@options_command(RunCliOptions)
def run(ctx: typer.Context, opts: RunCliOptions) -> None:
    """Claim and drive items until STOP (or one pass with --once)."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        reports = build_runner(opts).run(once=opts.once)
    except (Refused, HarnessConfigError, GitError, KeyError, AwgError) as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(2) from exc
    for report in reports:
        typer.echo(f"{report.outcome}\t{report.ref or '-'}\t{report.detail}")


@app.command("stop")
def stop(state_dir: Path | None = _STATE) -> None:
    """Create STOP and kill every registered worker process group."""
    killed = request_stop(state_of(state_dir))
    typer.echo(f"STOP set; killed {killed} worker group(s)")


@app.command("pause")
def pause(project: str = _PROJECT, state_dir: Path | None = _STATE) -> None:
    """Pause intake for one project."""
    set_paused(state_of(state_dir), project, True)
    typer.echo(f"paused intake for {project}")


@app.command("resume")
def resume(project: str = _PROJECT, state_dir: Path | None = _STATE) -> None:
    """Resume intake for one project."""
    set_paused(state_of(state_dir), project, False)
    typer.echo(f"resumed intake for {project}")


@app.command("intake")
@options_command(IntakeOptions)
def intake(ctx: typer.Context, opts: IntakeOptions) -> None:
    """Pull labelled GitHub issues into AWG as runner items (`awg sync github`)."""
    try:
        report = run_sync(awg_binary(opts.awg_bin), sync_argv(opts))
    except (Refused, HarnessConfigError, AwgError) as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(2) from exc
    for line in summary(report):
        typer.echo(line)
