"""Blueprint summary display for CLI."""
from __future__ import annotations

from rich.console import Console
from rich.table import Table

console = Console()


def cmd_blueprints(client) -> None:
    """Show stored task blueprints."""
    try:
        data = client.blueprints()
    except (Exception, SystemExit):
        data = []
    if not data:
        console.print("[dim]No blueprints recorded yet.[/dim]")
        return
    t = Table(title="Task Blueprints")
    t.add_column("Type", style="bold")
    t.add_column("Keywords")
    t.add_column("Tools", justify="right")
    t.add_column("Model")
    t.add_column("Conf", justify="right")
    t.add_column("Uses", justify="right")
    for bp in data[:20]:
        _add_row(t, bp)
    console.print(t)


def _add_row(t: Table, bp: dict) -> None:
    """Add one blueprint row to the table."""
    kw = ", ".join(bp.get("keywords", [])[:4])
    if len(kw) > 30:
        kw = kw[:27] + "..."
    tools = str(len(bp.get("tool_sequence", [])))
    succ = bp.get("success_count", 0)
    fail = bp.get("fail_count", 0)
    total = succ + fail
    conf = succ / total if total else 0
    tag = "green" if conf >= 0.8 else "yellow"
    t.add_row(
        bp.get("task_type", "?"), kw, tools,
        bp.get("min_model", "?"),
        f"[{tag}]{conf:.0%}[/{tag}]", str(succ),
    )
