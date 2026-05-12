"""REPL slash command handlers for Maggy CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

console = Console()

_KNOWN_MODELS = ("local", "kimi", "gpt", "claude", "codex")


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


def dispatch(cmd: str, client, state: SessionState) -> bool:
    """Route a slash command. Returns True if handled."""
    parts = cmd.strip().split(None, 1)
    name, args = parts[0].lower(), parts[1] if len(parts) > 1 else ""
    simple = {
        "/stats": cmd_stats, "/budget": cmd_budget,
        "/route": cmd_route, "/models": cmd_models,
        "/config": cmd_config, "/health": cmd_health,
    }
    if name in simple:
        simple[name](client)
        return True
    if name == "/use":
        cmd_use(args, state)
    elif name == "/claude-md":
        cmd_claude_md(state)
    elif name == "/help":
        cmd_help()
    else:
        return False
    return True


def cmd_stats(client) -> None:
    b = _call(client.budget_summary)
    t = Table(title="Stats")
    t.add_column("Metric", style="bold")
    t.add_column("Value")
    t.add_row("Spent", f"${b.get('spent_today_usd', 0):.2f} / ${b.get('daily_limit_usd', 0):.2f}")
    in_t, out_t = b.get("input_tokens", 0), b.get("output_tokens", 0)
    if in_t or out_t:
        t.add_row("Tokens", f"{in_t:,} in / {out_t:,} out")
    t.add_row("Status", b.get("status", "?"))
    for p in _call(client.budget_by_provider, []):
        t.add_row(f"  {p.get('provider', '?')}", f"${p.get('spent_usd', 0):.2f}")
    for h in _call(client.models_heatmap, [])[:8]:
        r, c = h.get("avg_reward", 0), "green" if h.get("avg_reward", 0) >= 0.8 else "yellow"
        t.add_row(f"  {h.get('model', '?')} ({h.get('task_type', '')})", f"[{c}]{r:.2f}[/{c}] ({h.get('samples', 0)})")
    console.print(t)


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
            t.add_row(h.get("model", "?"), h.get("task_type", "?"), h.get("blast_tier", "?"), f"[{c}]{r:.2f}[/{c}]", str(h.get("samples", 0)))
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
        console.print(f"[yellow]Unknown: {', '.join(bad)}. Known: {', '.join(_KNOWN_MODELS)}[/yellow]")
    state.allowed_models = models
    console.print(f"[dim]Routing restricted to: {', '.join(models)}[/dim]")


def cmd_config(client) -> None:
    """Show configuration summary."""
    cfg = _call(client.config)
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    cbs = cfg.get("codebases", [])
    t.add_row("Codebases", str(len(cbs)))
    for cb in cbs[:5]:
        t.add_row(f"  {cb.get('key', '?')}", cb.get("path", ""))
    t.add_row("Routing", cfg.get("routing", {}).get("mode", "dynamic"))
    t.add_row("Limit", f"${cfg.get('budget', {}).get('daily_limit_usd', 0):.2f}")
    console.print(Panel(t, title="Config", border_style="blue"))


def cmd_claude_md(state: SessionState) -> None:
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
    mn, score = data.get("mnemos", {}), eng.get("health_score", 0)
    c = "green" if score >= 0.7 else "yellow" if score >= 0.4 else "red"
    t = Table(show_header=False, box=None, padding=(0, 2))
    t.add_column(style="bold")
    t.add_column()
    t.add_row("Engram", f"[{c}]{score:.0%}[/{c}] ({eng.get('active', 0)}/{eng.get('total', 0)})")
    t.add_row("Mnemos", f"{mn.get('state', '?')} ({mn.get('composite', 0):.2f})")
    console.print(Panel(t, title="Health", border_style="green"))


_HELP = """\
[bold]Commands:[/bold]
  /stats   Budget+perf      /budget  Breakdown       /route   Rules+tiers
  /models  Reward heatmap   /health  Memory health   /monitor Trackers
  /screenshot F  Analyze image with Qwen3-VL         /claude-md CLAUDE.md
  /use M   Restrict models  /config  Settings        /blast N Override
  /history Messages         /sessions List           /clear   Screen
  /quit    Exit             /help    This help"""


def cmd_help() -> None:
    console.print(_HELP)
