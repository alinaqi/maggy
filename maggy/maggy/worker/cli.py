"""`maggy worker run`: one local worker attempt through the full runner pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer

from maggy.harness.cli.command import options_command
from maggy.harness.errors import HarnessConfigError
from maggy.worker.assemble import RunOptions, local_attempt
from maggy.worker.git_ops import GitError
from maggy.worker.launch import Refused
from maggy.worker.pipeline import run_attempt

app = typer.Typer(help="Headless worker runs (adapters, runner-side commit and checks).",
                  no_args_is_help=True)


@dataclass
class RunCliOptions:
    adapter: str = typer.Option(..., "--adapter", help="Adapter name (claude, codex, ...).")
    repo: Path = typer.Option(Path("."), "--repo", help="Git repository to work in.")
    prompt_file: Path = typer.Option(..., "--prompt-file", exists=True, dir_okay=False,
                                     help="File holding the prompt.")
    permission: str | None = typer.Option(None, "--permission",
                                          help="Permission profile (default: worker.permission).")
    deadline: int | None = typer.Option(None, "--deadline", min=1, help="Deadline in seconds.")
    budget: float | None = typer.Option(None, "--budget", min=0.0, help="Per-run budget in USD.")


@app.command("run")
@options_command(RunCliOptions)
def run(ctx: typer.Context, opts: RunCliOptions) -> None:
    """Run one attempt in a new worktree and print the WorkerResult as JSON."""
    options = RunOptions(opts.adapter, opts.repo, opts.prompt_file.read_text(),
                         opts.permission, opts.deadline, opts.budget)
    try:
        result = run_attempt(local_attempt(options))
    except (Refused, HarnessConfigError, GitError, KeyError) as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(result.model_dump_json(indent=2))
