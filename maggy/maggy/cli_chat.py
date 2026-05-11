"""Interactive chat REPL for Maggy CLI with model routing."""

from __future__ import annotations

import os

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.table import Table

from maggy.services.session_detect import detect_all

console = Console()


def detect_project(client) -> str | None:
    """Auto-detect project from current working directory."""
    return client.detect_project(os.getcwd())


def run_chat(
    client, project: str, routed: bool = True,
) -> None:
    """Main chat REPL loop with session resume."""
    session, resumed = _find_or_create(client, project)
    sid = session.get("id", "?")
    wd = session.get("working_dir", "?")
    label = "Resuming" if resumed else "New session"
    n = session.get("messages", 0)
    suffix = f", {n} msgs" if resumed else ""
    console.print(
        f"{label} [bold]{project}[/bold] ({sid}{suffix})",
    )
    console.print(f"Working dir: {wd}")
    _show_resume_info(client, sid, wd)
    mode = "routed" if routed else "direct"
    console.print(
        f"[dim]Mode: {mode} | "
        f"/blast N /history /sessions /quit[/dim]\n",
    )
    _repl_loop(client, sid, routed)
    console.print("[dim]Session saved. Bye.[/dim]")


def _find_or_create(
    client, project: str,
) -> tuple[dict, bool]:
    """Find existing session or create new one."""
    for s in client.chat_sessions():
        if s.get("project_key") == project:
            return s, True
    return client.chat_create(project), False


def _show_resume_info(
    client, sid: str, wd: str,
) -> None:
    """Show detected CLI sessions and recent messages."""
    detected = detect_all(wd)
    if detected.sessions:
        parts = [
            f"{s.cli}({s.session_id[:8]})"
            for s in detected.sessions
        ]
        console.print(
            f"[dim]Prior: {', '.join(parts)}[/dim]",
        )
    data = client.chat_history(sid)
    msgs = data.get("messages", [])[-3:]
    if not msgs:
        return
    console.print("[dim]--- Recent ---[/dim]")
    for msg in msgs:
        role = msg.get("role", "?")
        text = msg.get("content", "")[:120]
        tag = "[cyan]You[/cyan]" if role == "user" else "[green]Maggy[/green]"
        console.print(f"  {tag}: {text}")
    console.print()


def _repl_loop(
    client, session_id: str, routed: bool,
) -> None:
    """Prompt loop with blast override support."""
    blast_override: int | None = None
    while True:
        try:
            text = Prompt.ask("[bold cyan]maggy[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print()
            break
        stripped = text.strip()
        if not stripped:
            continue
        if stripped == "/quit":
            break
        if stripped == "/history":
            _show_history(client, session_id)
            continue
        if stripped == "/sessions":
            _show_sessions(client)
            continue
        if stripped == "/clear":
            console.clear()
            continue
        if stripped.startswith("/blast"):
            blast_override = _parse_blast(stripped)
            continue
        if routed:
            chunks = client.chat_send_routed(
                session_id, stripped, blast=blast_override,
            )
        else:
            chunks = client.chat_send_stream(
                session_id, stripped,
            )
        _stream_chunks(chunks)
        blast_override = None


def _parse_blast(text: str) -> int | None:
    """Parse /blast N command."""
    parts = text.split()
    if len(parts) >= 2:
        try:
            val = max(1, min(10, int(parts[1])))
            console.print(f"[dim]Blast override: {val}[/dim]")
            return val
        except ValueError:
            pass
    console.print("[dim]Usage: /blast N (1-10)[/dim]")
    return None


def _stream_chunks(chunks) -> None:
    """Stream and display response chunks from any model."""
    full, err = "", ""
    try:
        with Live(
            Markdown(""), console=console,
            refresh_per_second=8,
        ) as live:
            for chunk in chunks:
                ct = chunk.get("type", "")
                if ct == "routing":
                    m = chunk.get("model", "?")
                    b = chunk.get("blast", "?")
                    r = chunk.get("reason", "")
                    console.print(
                        f"[dim][{m}] blast={b} {r}[/dim]",
                    )
                elif ct in ("text", "result"):
                    full += chunk.get("content", "")
                    live.update(Markdown(full))
                elif ct == "error":
                    err = chunk.get("content", "")
                elif ct == "done":
                    break
    except Exception as e:
        err = str(e)
    if err:
        console.print(f"[red]Error:[/red] {err}")


def _show_history(client, session_id: str) -> None:
    """Display message history."""
    msgs = client.chat_history(session_id).get("messages", [])
    if not msgs:
        console.print("[dim]No messages yet.[/dim]")
        return
    for msg in msgs:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        if role == "user":
            console.print(f"\n[bold cyan]You:[/bold cyan] {content}")
        else:
            console.print("\n[bold green]Maggy:[/bold green]")
            console.print(Markdown(content))


def _show_sessions(client) -> None:
    """List all active sessions."""
    sessions = client.chat_sessions()
    if not sessions:
        console.print("[dim]No chat sessions.[/dim]")
        return
    t = Table(title="Chat Sessions")
    t.add_column("ID", width=12)
    t.add_column("Project")
    t.add_column("Status")
    t.add_column("Messages", justify="right")
    for s in sessions:
        t.add_row(
            s.get("id", "?"), s.get("project_key", "?"),
            s.get("status", "?"), str(s.get("messages", 0)),
        )
    console.print(t)
