"""Maggy CLI — terminal interface for the engineering platform."""

from __future__ import annotations

import typer

from maggy.cli_client import MaggyClient
from maggy.cli_output import (
    console,
    dump_json,
    render_budget,
    render_competitors,
    render_health,
    render_inbox,
    render_models,
    render_route,
    render_sessions,
)

app = typer.Typer(
    name="maggy",
    help="Maggy — AI Engineering Platform",
    no_args_is_help=False,
)

_client = MaggyClient()


def _ensure() -> bool:
    if not _client.ensure_server():
        console.print("[red]Cannot reach Maggy server.[/red]")
        raise typer.Exit(1)
    return True


# ── Default: launch dashboard ───────────────────


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Launch the Maggy dashboard (default)."""
    if ctx.invoked_subcommand is None:
        serve()


# ── Serve ───────────────────────────────────────


@app.command()
def serve() -> None:
    """Start the Maggy server + web dashboard."""
    from maggy.main import main as start_server
    start_server()


# ── Status ──────────────────────────────────────


@app.command()
def status(
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show server health and config summary."""
    _ensure()
    data = _client.health()
    if json_out:
        dump_json(data)
    else:
        render_health(data)


# ── Inbox ───────────────────────────────────────


@app.command()
def inbox(
    refresh: bool = typer.Option(False, "--refresh"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show AI-ranked task inbox."""
    _ensure()
    data = _client.inbox(refresh=refresh)
    if json_out:
        dump_json(data)
    elif not data.get("items"):
        console.print("[dim]No tasks in inbox.[/dim]")
    else:
        render_inbox(data)


# ── Sessions ────────────────────────────────────


@app.command()
def sessions(
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """List active AI sessions across projects."""
    _ensure()
    data = _client.activity()
    if json_out:
        dump_json(data)
    else:
        render_sessions(data)


# ── Execute ─────────────────────────────────────


@app.command()
def execute(
    task_id: str = typer.Argument(..., help="Task ID"),
    plan: bool = typer.Option(False, "--plan"),
) -> None:
    """Execute a task via the TDD pipeline."""
    _ensure()
    mode = "plan" if plan else "tdd"
    data = _client.execute(task_id, mode)
    console.print(
        f"[green]Started[/green] session "
        f"[bold]{data.get('session_id', '?')}[/bold] "
        f"({mode} mode)",
    )


# ── Route ───────────────────────────────────────


@app.command()
def route(
    blast: int = typer.Argument(..., help="Complexity 1-10"),
    task_type: str = typer.Option("general", "--type"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Get routing decision for a complexity score."""
    _ensure()
    data = _client.route(blast, task_type)
    if json_out:
        dump_json(data)
    else:
        render_route(data)


# ── Budget ──────────────────────────────────────


@app.command()
def budget(
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show per-provider token budget."""
    _ensure()
    data = _client.budget_summary()
    if json_out:
        dump_json(data)
    else:
        render_budget(data)


# ── Models ──────────────────────────────────────


@app.command()
def models(
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show model performance heatmap."""
    _ensure()
    data = _client.models_heatmap()
    if json_out:
        dump_json(data)
    else:
        render_models(data)


# ── Competitors ─────────────────────────────────


@app.command()
def competitors(
    briefing: bool = typer.Option(False, "--briefing"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show competitor intelligence."""
    _ensure()
    if briefing:
        data = _client.competitors_briefing()
    else:
        data = _client.competitors_news()
    if json_out:
        dump_json(data)
    elif briefing:
        console.print(data.get("summary", "No briefing available."))
    else:
        render_competitors(data)


# ── Process ─────────────────────────────────────


@app.command()
def process(
    project: str = typer.Argument(..., help="Project key"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show process health for a project."""
    _ensure()
    data = _client.process_health(project)
    if json_out:
        dump_json(data)
    else:
        console.print_json(data=data)


# ── Config ──────────────────────────────────────


@app.command()
def config(
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show current configuration (redacted)."""
    _ensure()
    data = _client.config()
    dump_json(data)
