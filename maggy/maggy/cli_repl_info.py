"""REPL info command handlers — session, history, health."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()


def _call(fn, d=None):
    try:
        return fn()
    except (Exception, SystemExit):
        return d if d is not None else {}


def cmd_config(client) -> None:
    """Show configuration summary."""
    cfg = _call(client.config)
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    cbs = cfg.get("codebases", [])
    t.add_row("Codebases", str(len(cbs)))
    for cb in cbs[:5]:
        t.add_row(
            f"  {cb.get('key', '?')}", cb.get("path", ""),
        )
    t.add_row(
        "Routing",
        cfg.get("routing", {}).get("mode", "dynamic"),
    )
    t.add_row(
        "Limit",
        f"${cfg.get('budget', {}).get('daily_limit_usd', 0):.2f}",
    )
    console.print(Panel(t, title="Config", border_style="blue"))


def cmd_claude_md(state) -> None:
    """Show project's CLAUDE.md."""
    wd = Path(state.working_dir)
    for name in ("CLAUDE.md", ".claude/CLAUDE.md"):
        path = wd / name
        if path.exists():
            console.print(Markdown(path.read_text()))
            return
    console.print("[dim]CLAUDE.md not found in project.[/dim]")


def cmd_health(client) -> None:
    """Memory system health dashboard."""
    data = _call(client.health_dashboard)
    eng = data if "health_score" in data else data.get("engram", {})
    mn = data.get("mnemos", {})
    score = eng.get("health_score", 0)
    c = "green" if score >= 0.7 else "yellow" if score >= 0.4 else "red"
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    t.add_row(
        "Engram",
        f"[{c}]{score:.0%}[/{c}]"
        f" ({eng.get('active', 0)}/{eng.get('total', 0)})",
    )
    t.add_row(
        "Mnemos",
        f"{mn.get('state', '?')} ({mn.get('composite', 0):.2f})",
    )
    console.print(Panel(t, title="Health", border_style="green"))


def cmd_history(client, state) -> None:
    """Show recent messages in this session."""
    msgs = _call(
        lambda: client.chat_history(state.session_id),
    ).get("messages", [])
    if not msgs:
        console.print("[dim]No messages yet.[/dim]")
        return
    for msg in msgs:
        role = msg.get("role", "?")
        content = msg.get("content", "")
        tag = "[cyan]You[/cyan]" if role == "user" else "[green]Maggy[/green]"
        console.print(f"  {tag}: {content[:120]}")


def cmd_sessions(client) -> None:
    """List active chat sessions."""
    sessions = _call(client.chat_sessions, [])
    if not sessions:
        console.print("[dim]No chat sessions.[/dim]")
        return
    for s in sessions:
        sid = s.get("id", "?")[:8]
        proj = s.get("project_key", "?")
        n = s.get("messages", 0)
        console.print(f"  [bold]{sid}[/bold] {proj} ({n} msgs)")


def cmd_thinking(state) -> None:
    """Show last response's tool events."""
    events = state.last_tool_events
    if not events:
        console.print("[dim]No tool events from last response.[/dim]")
        return
    for event in events:
        console.print(f"  [dim cyan]> {event}[/dim cyan]")
