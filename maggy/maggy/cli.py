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
    if not _client._check_health():
        console.print("[dim]Starting Maggy server...[/dim]")
    if not _client.ensure_server():
        console.print("[red]Cannot reach Maggy server.[/red]")
        raise typer.Exit(1)
    return True


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Interactive REPL (in project) or dashboard."""
    if ctx.invoked_subcommand is not None:
        return
    _ensure()
    from maggy.cli_chat import detect_project, run_chat
    project = detect_project(_client)
    if project:
        run_chat(_client, project, routed=True)
    else:
        serve()


@app.command()
def serve() -> None:
    """Start the Maggy server + web dashboard."""
    from maggy.main import main as start_server
    start_server()


@app.command()
def status(json_out: bool = typer.Option(False, "--json")) -> None:
    """Show server health and config summary."""
    _ensure()
    data = _client.health()
    dump_json(data) if json_out else render_health(data)


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


@app.command()
def sessions(json_out: bool = typer.Option(False, "--json")) -> None:
    """List active AI sessions across projects."""
    _ensure()
    data = _client.activity()
    dump_json(data) if json_out else render_sessions(data)


@app.command()
def chat(
    project: str = typer.Argument(..., help="Project key"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Interactive chat with a project's AI session."""
    _ensure()
    from maggy.cli_chat import run_chat
    run_chat(_client, project, routed=not direct)


@app.command()
def spawn(
    task: str = typer.Argument(..., help="Task description"),
) -> None:
    """Spawn a background AI session."""
    _ensure()
    from maggy.cli_chat import detect_project
    from maggy.cli_sessions import spawn_session
    project = detect_project(_client)
    if not project:
        console.print("[red]Not in a project directory.[/red]")
        raise typer.Exit(1)
    spawn_session(_client, task, project)


@app.command()
def ps() -> None:
    """List all managed sessions (chat + executor)."""
    _ensure()
    from maggy.cli_sessions import list_all
    list_all(_client)


@app.command()
def kill(
    session_id: str = typer.Argument(..., help="Session ID"),
) -> None:
    """Stop a managed session."""
    _ensure()
    from maggy.cli_sessions import kill_session
    kill_session(_client, session_id)


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


@app.command()
def route(
    blast: int = typer.Argument(..., help="Complexity 1-10"),
    task_type: str = typer.Option("general", "--type"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Get routing decision for a complexity score."""
    _ensure()
    data = _client.route(blast, task_type)
    dump_json(data) if json_out else render_route(data)


@app.command()
def budget(json_out: bool = typer.Option(False, "--json")) -> None:
    """Show per-provider token budget."""
    _ensure()
    data = _client.budget_summary()
    dump_json(data) if json_out else render_budget(data)


@app.command()
def models(json_out: bool = typer.Option(False, "--json")) -> None:
    """Show model performance heatmap."""
    _ensure()
    data = _client.models_heatmap()
    dump_json(data) if json_out else render_models(data)


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


@app.command()
def process(
    project: str = typer.Argument(..., help="Project key"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show process health for a project."""
    _ensure()
    data = _client.process_health(project)
    dump_json(data) if json_out else console.print_json(data=data)


@app.command()
def config(json_out: bool = typer.Option(False, "--json")) -> None:
    """Show current configuration (redacted)."""
    _ensure()
    dump_json(_client.config())
