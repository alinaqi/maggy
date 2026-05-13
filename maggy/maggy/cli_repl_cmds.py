"""REPL slash command handlers for Maggy CLI."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from maggy.cli_repl_info import (
    cmd_cancel,
    cmd_claude_md,
    cmd_config,
    cmd_health,
    cmd_history,
    cmd_sessions,
    cmd_stats,
    cmd_status,
    cmd_thinking,
)
from maggy.cli_blueprints import cmd_blueprints
from maggy.cli_rules import cmd_rules

console = Console()

_KNOWN_MODELS = ("local", "kimi", "claude", "codex")


def _call(fn, d=None):
    try:
        return fn()
    except (Exception, SystemExit):
        return d if d is not None else {}


@dataclass
class SessionState:
    """Mutable session-level state for REPL."""

    session_id: str = ""
    working_dir: str = ""
    allowed_models: list[str] = field(default_factory=list)
    last_tool_events: list[str] = field(default_factory=list)
    bg_task: object | None = None


def dispatch(cmd: str, client, state: SessionState) -> bool:
    """Route a slash command. Returns True if handled."""
    parts = cmd.strip().split(None, 1)
    name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    simple = {"/stats": cmd_stats, "/budget": cmd_budget, "/route": cmd_route, "/models": cmd_models, "/rules": cmd_rules, "/blueprints": cmd_blueprints}
    if name in simple:
        simple[name](client)
        return True
    if name == "/use":
        cmd_use(args, state)
    elif name == "/config":
        cmd_config(client)
    elif name == "/health":
        cmd_health(client)
    elif name == "/claude-md":
        cmd_claude_md(state)
    elif name == "/history":
        cmd_history(client, state)
    elif name == "/sessions":
        cmd_sessions(client)
    elif name == "/monitor":
        console.print(f"[dim]Monitors: {_call(client.monitor_status).get('active', 0)} active[/dim]")
    elif name == "/thinking":
        cmd_thinking(state)
    elif name == "/status":
        cmd_status(state)
    elif name == "/cancel":
        cmd_cancel(state)
    elif name == "/reviewers":
        cmd_reviewers(client)
    elif name == "/help":
        cmd_help()
    else:
        return False
    return True


def cmd_budget(client) -> None:
    b = _call(client.budget_summary)
    spent, limit = b.get("spent_today_usd", 0), b.get("daily_limit_usd", 0)
    pct = (spent / limit * 100) if limit else 0
    bl, c = min(20, int(pct / 5)), "red" if pct > 80 else "green"
    bar = f"[{c}]{'█' * bl}[/{c}]{'░' * (20 - bl)}"
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    if b.get("plan") == "subscription":
        t.add_row("Plan", "[green]Subscription[/green]")
    else:
        t.add_row("Spent", f"${spent:.2f} / ${limit:.2f}")
    t.add_row("Usage", f"{pct:.0f}%  {bar}")
    t.add_row("Status", b.get("status", "?"))
    for p in _call(client.budget_by_provider, []):
        t.add_row(p.get("provider", "?"), f"${p.get('spent_usd', 0):.2f}")
    console.print(Panel(t, title="Budget", border_style="green"))


def cmd_route(client) -> None:
    data = _call(client.routing_rules)
    t = Table(title=f"Routing ({data.get('mode', '?')})")
    t.add_column("Task Type", style="bold")
    t.add_column("Model")
    t.add_column("Reason", style="dim")
    for tt, info in data.get("task_type_overrides", {}).items():
        t.add_row(tt, info.get("model", "?"), info.get("reason", ""))
    console.print(t)
    console.print("[dim]Blast: 1-3 cheap | 4-6 medium | 7-10 premium[/dim]")
    perf = data.get("model_performance", {})
    if not perf:
        return
    pt = Table(title="Model Performance")
    pt.add_column("Model", style="bold")
    pt.add_column("Strengths")
    pt.add_column("Rate", justify="right")
    for model, info in perf.items():
        pt.add_row(model, ", ".join(info.get("strengths", [])), f"{info.get('success_rate', 0):.0%}")
    console.print(pt)


def cmd_models(client) -> None:
    heatmap = _call(client.models_heatmap, [])
    t = Table(title="Model Rewards")
    for col in ("Model", "Task Type", "Blast Tier"):
        t.add_column(col)
    t.add_column("Reward", justify="right")
    t.add_column("N", justify="right")
    if not heatmap:
        for m in _KNOWN_MODELS:
            t.add_row(m, "-", "-", "-", "0")
    else:
        for h in heatmap:
            r = h.get("avg_reward", 0)
            c = "green" if r >= 0.8 else "yellow" if r >= 0.5 else "red"
            t.add_row(
                h.get("model", "?"),
                h.get("task_type", "?"),
                h.get("blast_tier", "?"),
                f"[{c}]{r:.2f}[/{c}]",
                str(h.get("samples", 0)),
            )
    console.print(t)


def cmd_use(args: str, state: SessionState) -> None:
    """Set allowed models for this session."""
    if not args or args.strip().lower() == "all":
        state.allowed_models = []
        console.print("[dim]Routing: all models enabled[/dim]")
        return
    models = [m.strip() for m in args.split(",") if m.strip()]
    bad = [m for m in models if m not in _KNOWN_MODELS]
    if bad:
        console.print(
            f"[yellow]Unknown: {', '.join(bad)}."
            f" Known: {', '.join(_KNOWN_MODELS)}[/yellow]",
        )
    state.allowed_models = models
    console.print(
        f"[dim]Routing restricted to: {', '.join(models)}[/dim]",
    )


_HELP = """\
[bold]Commands:[/bold]
  /stats  Budget+perf   /budget  Breakdown    /route  Rules+tiers  /models Rewards
  /health Memory        /monitor Trackers     /config Settings     /claude-md CLAUDE.md
  /use M  Restrict      /blast N Override     /screenshot F Vision /thinking Tools
  /history Messages     /sessions List        /reviewers Eval       /rules Summary
  /blueprints Recipes   /status Background    /cancel Stop bg       /clear Screen
  /quit   Exit          /help   This help"""


def cmd_reviewers(client) -> None:
    """Show reviewer performance heatmap."""
    hm = _call(client.reviewer_heatmap, [])
    if not hm:
        console.print("[dim]No reviewer data yet.[/dim]")
        return
    t = Table(title="Reviewer Eval")
    for col in ("Reviewer", "Category"):
        t.add_column(col)
    t.add_column("Score", justify="right")
    t.add_column("N", justify="right")
    for r in hm:
        s, c = r.get("avg_score", 0), "yellow"
        c = "green" if s >= 0.7 else "yellow" if s >= 0.4 else "red"
        t.add_row(r.get("reviewer", "?"), r.get("category", "?"), f"[{c}]{s:.2f}[/{c}]", str(r.get("samples", 0)))
    console.print(t)


def cmd_help() -> None:
    console.print(_HELP)
