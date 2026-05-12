"""Rich welcome banner for Maggy CLI startup."""

from __future__ import annotations

import os
import shutil

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

VERSION = "0.5"


def render_welcome(
    project: str, session: dict, client,
) -> None:
    """Print a rich 2-column welcome panel."""
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    _add_project_rows(t, project, session)
    _add_system_rows(t, client, session)
    label = "Resuming" if session.get("messages", 0) else "New"
    title = f"Maggy v{VERSION} - {label}"
    console.print(Panel(t, title=title, border_style="cyan"))
    console.print(
        "[dim]/help for commands | /stats for budget[/dim]\n",
    )
    _pad_to_bottom(panel_rows=8)


def _add_project_rows(
    t: Table, project: str, session: dict,
) -> None:
    """Left-side project info."""
    wd = session.get("working_dir") or os.getcwd()
    short_wd = _shorten(wd, 35)
    msgs = session.get("messages", 0)
    sid = session.get("id", "?")[:8]
    t.add_row("Project", f"[bold]{project}[/bold]")
    t.add_row("Dir", short_wd)
    t.add_row("Session", f"{sid} ({msgs} msgs)")


_KNOWN_MODELS = ("local", "kimi", "gpt", "claude", "codex")


def _add_system_rows(
    t: Table, client, session: dict,
) -> None:
    """Right-side system state."""
    budget = _safe_call(client.budget_summary)
    if isinstance(budget, dict) and budget.get("plan") == "subscription":
        t.add_row("Budget", "[green]Subscription[/green]")
    else:
        spent = budget.get("spent_today_usd", 0) if isinstance(budget, dict) else 0
        limit = budget.get("daily_limit_usd", 0) if isinstance(budget, dict) else 0
        t.add_row("Budget", f"${spent:.2f} / ${limit:.2f}")
    models = _safe_call(client.models_heatmap)
    count = len(models) if models else len(_KNOWN_MODELS)
    label = f"{len(models)} tracked" if models else f"{count} available"
    t.add_row("Models", label)
    status = budget.get("status", "?") if isinstance(budget, dict) else "?"
    t.add_row("Status", f"[green]{status}[/green]")
    _add_health_row(t, client)


def _add_health_row(t: Table, client) -> None:
    """Show engram health score inline."""
    diag = _safe_call(client.engram_diagnostics)
    if not isinstance(diag, dict):
        return
    score = diag.get("health_score", 0)
    color = "green" if score >= 0.7 else "yellow" if score >= 0.4 else "red"
    t.add_row("Memory", f"[{color}]{score:.0%}[/{color}]")


def _safe_call(fn):
    """Call a client method, return empty on failure."""
    try:
        return fn() or []
    except Exception:
        return []


def _pad_to_bottom(panel_rows: int = 8) -> None:
    """Print blank lines to push prompt near terminal bottom."""
    term_h = shutil.get_terminal_size().lines
    used = panel_rows + 3  # panel + help line + blank + prompt
    pad = max(0, term_h - used)
    if pad:
        console.print("\n" * (pad - 1), end="")


def _shorten(path: str, max_len: int) -> str:
    """Truncate long paths with ellipsis."""
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3) :]
