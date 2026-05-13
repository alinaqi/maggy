"""Rich streaming display — spinner, tool progress, markdown."""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.text import Text

_QUOTA_MARKERS = ("rate_limit", "quota", "exceeded", "429")

_PATH_TOOLS = {
    "Read": "file_path",
    "Edit": "file_path",
    "Write": "file_path",
    "Grep": "pattern",
    "Glob": "pattern",
}


@dataclass
class _StreamState:
    """Mutable state for the stream display."""

    console: Console
    content: str = ""
    error: str = ""
    tool_events: list[str] = None

    def __post_init__(self):
        if self.tool_events is None:
            self.tool_events = []

    def __rich__(self) -> Group:
        """Called by Live on every auto-refresh tick."""
        return _build_display(self)


def _build_display(state: _StreamState) -> Group:
    """Compose spinner or content for Live area."""
    if state.content:
        return Group(Markdown(state.content))
    return Group(Spinner("dots", text="Thinking..."))


def _format_tool_use(tool: str, inp: dict) -> str:
    """Format tool name and key input as label."""
    key = _PATH_TOOLS.get(tool)
    if key and key in inp:
        path = str(inp[key])
        parts = path.rsplit("/", 2)
        short = "/".join(parts[-2:]) if len(parts) > 2 else path
        return f"{tool} {short}"
    if tool == "Bash":
        cmd = str(inp.get("command", ""))[:50]
        return f"$ {cmd}"
    if tool == "Task":
        return f"Agent: {inp.get('description', '')}"
    return tool


def _handle_chunk(state: _StreamState, chunk: dict) -> bool:
    """Process one SSE chunk. Returns False on 'done'."""
    ct = chunk.get("type", "")
    if ct == "routing":
        model = chunk.get("model", "")
        state.console.print(Text(f"  {model}", style="dim"))
    elif ct == "tool_use":
        label = _format_tool_use(
            chunk.get("tool", ""), chunk.get("input", {}),
        )
        state.tool_events.append(label)
        state.console.print(
            Text(f"  > {label}", style="dim cyan"),
        )
    elif ct == "queued":
        pos = chunk.get("position", "?")
        state.console.print(f"[dim]Queued ({pos})[/dim]")
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


def _show_tool_summary(state: _StreamState) -> None:
    """Print collapsed summary of tool events."""
    n = len(state.tool_events)
    if n > 0:
        state.console.print(
            Text(f"  [{n} tool calls]", style="dim"),
        )


def stream_chunks(
    chunks: Iterable[dict], console: Console,
) -> dict:
    """Stream SSE chunks with spinner and tool progress."""
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
    _show_tool_summary(state)
    return {"tool_events": list(state.tool_events)}
