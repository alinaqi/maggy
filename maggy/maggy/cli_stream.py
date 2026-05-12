"""Rich streaming display — spinner and markdown output."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.text import Text

_QUOTA_MARKERS = ("rate_limit", "quota", "exceeded", "429")


@dataclass
class _StreamState:
    """Mutable state for the stream display."""

    console: Console
    model_label: str = ""
    content: str = ""
    error: str = ""

    def __rich__(self) -> Group:
        """Called by Live on every auto-refresh tick."""
        return _build_display(self)


def _build_display(state: _StreamState) -> Group:
    """Compose spinner or content with model label."""
    parts: list = []
    if state.model_label:
        parts.append(Text(f"  {state.model_label}", style="dim"))
    if state.content:
        parts.append(Markdown(state.content))
    else:
        parts.append(Spinner("dots", text="Thinking…"))
    return Group(*parts)


def _handle_chunk(state: _StreamState, chunk: dict) -> bool:
    """Process one SSE chunk. Returns False on 'done'."""
    ct = chunk.get("type", "")
    if ct == "routing":
        state.model_label = chunk.get("model", "")
    elif ct == "queued":
        pos = chunk.get("position", "?")
        state.model_label = f"Queued ({pos})"
    elif ct in ("warning", "agent_status"):
        msg = chunk.get("content", chunk.get("status", ""))
        state.console.print(f"[dim]{msg}[/dim]")
    elif ct in ("text", "result"):
        state.content += chunk.get("content", "")
    elif ct == "error":
        state.error = chunk.get("content", "")
    elif ct == "done":
        return False
    return True


def _show_error(state: _StreamState) -> None:
    """Print error and quota guide if applicable."""
    if not state.error:
        return
    state.console.print(f"[red]Error:[/red] {state.error}")
    low = state.error.lower()
    if any(m in low for m in _QUOTA_MARKERS):
        from maggy.services.account_guide import render_switch_guide
        render_switch_guide("anthropic")


def stream_chunks(
    chunks: Iterable[dict], console: Console,
) -> None:
    """Stream SSE chunks with spinner and model label."""
    state = _StreamState(console=console)
    try:
        with Live(
            state, console=console, refresh_per_second=8,
        ) as live:
            for chunk in chunks:
                if not _handle_chunk(state, chunk):
                    break
            if state.content:
                live.update(Markdown(state.content))
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/dim]")
    except Exception as e:
        state.error = str(e)
    _show_error(state)
