"""`maggy worker replay`: run the replay set per agent and print a comparison table."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import typer

from maggy.harness.errors import HarnessConfigError
from maggy.worker.replay.report import render_table
from maggy.worker.replay.runner import ReplayOptions, run_replay
from maggy.worker.replay.tasks import load_tasks

AGENTS = "claude,codex,opencode,pi"


@dataclass
class ReplayCliOptions:
    agents: str = typer.Option(AGENTS, "--agents", help="Comma-separated adapter names.")
    tasks: str | None = typer.Option(None, "--tasks", help="Comma-separated task ids "
                                     "(default: all five).")
    live: bool = typer.Option(False, "--live", help="Run the real CLIs (model calls, spend). "
                              "Default: fake CLIs replaying recorded output.")
    budget: float = typer.Option(0.25, "--budget", min=0.0, help="Per-run budget in USD.")
    deadline: int = typer.Option(300, "--deadline", min=1, help="Per-run deadline in seconds.")
    model: list[str] = typer.Option([], "--model", help="agent=model, e.g. claude=haiku "
                                    "(repeatable).")
    work_dir: Path | None = typer.Option(None, "--work-dir", help="Parent dir for this run's "
                                         "fixture repos (default: system temp).")
    state_dir: Path | None = typer.Option(None, "--state-dir", help="Budget ledger, logs and "
                                          "STOP file (default: ~/.maggy live, work dir offline).")
    json_out: Path | None = typer.Option(None, "--json", help="Also write the JSON report here.")


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def replay_options(opts: ReplayCliOptions) -> ReplayOptions:
    """CLI values to ReplayOptions; a fresh run dir so earlier runs are never reused."""
    tasks = _split(opts.tasks) if opts.tasks else [task.id for task in load_tasks()]
    if opts.work_dir:
        opts.work_dir.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="maggy-replay-", dir=opts.work_dir))
    models = dict(item.split("=", 1) for item in opts.model if "=" in item)
    return ReplayOptions(agents=_split(opts.agents), tasks=tasks, work_dir=work,
                         live=opts.live, state_dir=opts.state_dir, budget_usd=opts.budget,
                         deadline_s=opts.deadline, models=models)


def replay(opts: ReplayCliOptions) -> None:
    try:
        report = run_replay(replay_options(opts))
    except (KeyError, HarnessConfigError) as exc:
        typer.echo(f"refused: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(f"{report.mode} replay in {report.work_dir}\n{render_table(report)}")
    if opts.json_out:
        opts.json_out.write_text(report.model_dump_json(indent=2))
