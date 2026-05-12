"""Rich welcome banner for Maggy CLI startup."""

from __future__ import annotations

import os
import shutil

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

VERSION = "0.6"


def render_welcome(
    project: str, session: dict, client,
) -> None:
    """Print a minimal Claude Code-style welcome panel."""
    wd = session.get("working_dir") or os.getcwd()
    msgs = session.get("messages", 0)
    body = Text()
    body.append(f"\n  {wd}\n\n", style="dim")
    if msgs:
        body.append(f"  Resuming session ({msgs} msgs)\n", style="dim")
    body.append("  /help for commands\n", style="dim")
    console.print(Panel(
        body,
        title=f"Maggy v{VERSION} — {project}",
        border_style="cyan",
        expand=False,
    ))
    _pad_to_bottom(panel_rows=6 + (1 if msgs else 0))


def _pad_to_bottom(panel_rows: int = 6) -> None:
    """Print blank lines to push prompt near terminal bottom."""
    term_h = shutil.get_terminal_size().lines
    used = panel_rows + 2  # panel + prompt line
    pad = max(0, term_h - used)
    if pad:
        console.print("\n" * (pad - 1), end="")


def _shorten(path: str, max_len: int) -> str:
    """Truncate long paths with ellipsis."""
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3) :]
