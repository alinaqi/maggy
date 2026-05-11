"""Rich terminal formatters for Maggy CLI output."""

from __future__ import annotations

import json
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _is_pipe() -> bool:
    return not sys.stdout.isatty()


def dump_json(data) -> None:
    """Print raw JSON for piping / --json flag."""
    print(json.dumps(data, indent=2))


# ── Status ──────────────────────────────────────


def render_health(data: dict) -> None:
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    t.add_row("Status", f"[green]{data.get('status', '?')}[/green]")
    t.add_row("Mode", data.get("mode", "?"))
    t.add_row("Org", data.get("org", "?"))
    t.add_row("Codebases", str(data.get("codebases", 0)))
    t.add_row("Provider", data.get("provider", "?"))
    console.print(Panel(t, title="Maggy Status", border_style="blue"))


# ── Inbox ───────────────────────────────────────


def render_inbox(data: dict) -> None:
    items = data.get("items", [])
    if not items:
        console.print("[dim]No tasks in inbox.[/dim]")
        return
    t = Table(title=f"Inbox ({len(items)} tasks)")
    t.add_column("#", style="bold", width=4)
    t.add_column("Title", min_width=30)
    t.add_column("Labels")
    t.add_column("Reason", style="dim")
    for item in items:
        labels = ", ".join(item.get("labels", [])[:3])
        t.add_row(
            str(item.get("rank", "")),
            item.get("title", "")[:60],
            labels,
            item.get("ai_reason", "")[:40],
        )
    console.print(t)


# ── Sessions ────────────────────────────────────


def render_sessions(data: dict | list) -> None:
    items = data if isinstance(data, list) else data.get("sessions", [])
    if not items:
        console.print("[dim]No active sessions.[/dim]")
        return
    t = Table(title=f"Active Sessions ({len(items)})")
    t.add_column("PID", width=8)
    t.add_column("CLI")
    t.add_column("Project")
    t.add_column("Status")
    t.add_column("Agent")
    for s in items:
        cli = s.get("cli") or s.get("tool") or "?"
        agent = s.get("agent_name") or ""
        t.add_row(
            str(s.get("pid", "")),
            cli,
            s.get("project", "?"),
            s.get("status", "?"),
            agent,
        )
    console.print(t)


# ── Route ───────────────────────────────────────


def _model_name(val) -> str:
    if isinstance(val, dict):
        return val.get("name", "?")
    return str(val) if val else "?"


def render_route(data: dict) -> None:
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    primary = _model_name(data.get("primary"))
    t.add_row("Primary", f"[green]{primary}[/green]")
    validator = data.get("validator")
    if validator:
        t.add_row("Validator", _model_name(validator))
    fallback = data.get("fallback", [])
    if fallback:
        names = [_model_name(f) for f in fallback]
        t.add_row("Fallback", " → ".join(names))
    t.add_row("Reason", str(data.get("reason", "")))
    console.print(Panel(t, title="Routing Decision", border_style="yellow"))


# ── Budget ──────────────────────────────────────


def render_budget(data: dict) -> None:
    spent = data.get("spent_today_usd", 0)
    limit = data.get("daily_limit_usd", 0)
    pct = (spent / limit * 100) if limit else 0
    bar_len = int(pct / 5)
    color = "red" if pct > 80 else "green"
    bar = f"[{color}]{'█' * bar_len}[/{color}]{'░' * (20 - bar_len)}"

    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    t.add_row("Spent today", f"${spent:.2f}")
    t.add_row("Daily limit", f"${limit:.2f}")
    t.add_row("Utilization", f"{pct:.0f}%  {bar}")
    t.add_row("Status", data.get("status", "?"))

    # Per-provider breakdown if available
    providers = data.get("providers", [])
    if providers:
        t.add_row("", "")
        for p in providers:
            p_used = p.get("used", 0)
            p_limit = p.get("limit", 0)
            t.add_row(
                p.get("name", "?"),
                f"${p_used:.2f} / ${p_limit:.2f}",
            )
    console.print(Panel(t, title="Budget", border_style="green"))


# ── Competitors ─────────────────────────────────


def render_competitors(news: list) -> None:
    if not news:
        console.print("[dim]No competitor news.[/dim]")
        return
    t = Table(title=f"Competitor Intel ({len(news)} items)")
    t.add_column("Date", width=12)
    t.add_column("Type")
    t.add_column("Headline", min_width=40)
    for item in news[:20]:
        t.add_row(
            item.get("date", "?")[:10],
            item.get("event_type", "?"),
            item.get("headline", "")[:60],
        )
    console.print(t)


# ── Models ──────────────────────────────────────


def render_models(heatmap: list) -> None:
    if not heatmap:
        console.print("[dim]No model performance data.[/dim]")
        return
    t = Table(title="Model Performance Heatmap")
    t.add_column("Model")
    t.add_column("Task Type")
    t.add_column("Reward", justify="right")
    for entry in heatmap:
        reward = entry.get("reward", 0)
        color = "green" if reward >= 0.8 else "yellow" if reward >= 0.5 else "red"
        t.add_row(
            entry.get("model", "?"),
            entry.get("task_type", "?"),
            f"[{color}]{reward:.2f}[/{color}]",
        )
    console.print(t)
