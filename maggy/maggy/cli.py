"""Maggy CLI — terminal interface for the engineering platform."""

from __future__ import annotations

from pathlib import Path

import typer

from maggy.cli_analytics import register as _register_analytics
from maggy.cli_client import MaggyClient
from maggy.cli_output import (
    console,
    dump_json,
    render_health,
    render_inbox,
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
    """Interactive REPL — cwd is the project."""
    if ctx.invoked_subcommand is not None:
        return
    _ensure()
    from maggy.cli_chat import run_chat
    from maggy.cli_context import cwd_project
    name, path = cwd_project()
    run_chat(_client, name, path, routed=True)


@app.command()
def serve() -> None:
    """Start the Maggy server + web dashboard."""
    from maggy.main import main as start_server
    start_server()


@app.command()
def bootstrap(
    source: str = typer.Option(
        None, "--source", "-s",
        help="Path to a claude-bootstrap checkout (else $MAGGY_BOOTSTRAP_DIR or marker)",
    ),
) -> None:
    """Install Maggy's skills, hooks, commands, ~/bin model wrappers, and plugins."""
    from maggy.services.bootstrap import BootstrapError, run_bootstrap
    try:
        result = run_bootstrap(source)
    except BootstrapError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    console.print("[green]✓ Bootstrap installed:[/green]")
    for asset, n in result.items():
        console.print(f"  {asset}: {n}")
    console.print("\n[dim]Run [bold]maggy serve[/bold] to start the dashboard.[/dim]")


@app.command()
def restart() -> None:
    """Stop and restart the Maggy server."""
    console.print("[dim]Stopping Maggy server…[/dim]")
    _client._kill_stale_port()
    console.print("[dim]Starting Maggy server…[/dim]")
    if _client.ensure_server():
        console.print("[green]Maggy restarted.[/green]")
    else:
        console.print("[red]Failed to restart.[/red]")
        raise typer.Exit(1)


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
    project: str = typer.Argument(None, help="Project key"),
    direct: bool = typer.Option(False, "--direct"),
) -> None:
    """Interactive chat with a project's AI session."""
    _ensure()
    from maggy.cli_chat import run_chat
    from maggy.cli_context import cwd_project
    if project:
        name, path = project, str(Path.cwd().resolve())
    else:
        name, path = cwd_project()
    run_chat(_client, name, path, routed=not direct)


@app.command()
def spawn(
    task: str = typer.Argument(..., help="Task description"),
) -> None:
    """Spawn a background AI session."""
    _ensure()
    from maggy.cli_context import cwd_project
    from maggy.cli_sessions import spawn_session
    name, _path = cwd_project()
    spawn_session(_client, task, name)


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


# Register analytics/reporting commands (route, budget, models, etc.)
_register_analytics(app, _client, _ensure)
