"""Background task manager for non-blocking REPL."""
from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass, field

from rich.console import Console

from maggy.cli_stream import _format_tool_use, _handle_chunk


@dataclass
class TaskState:
    """Thread-safe state for a background streaming task."""

    status: str = "idle"
    chunks_received: int = 0
    tool_events: list[str] = field(default_factory=list)
    content: str = ""
    error: str = ""
    model: str = ""
    phase: str = ""
    cancel_event: threading.Event = field(
        default_factory=threading.Event,
    )
    lock: threading.Lock = field(
        default_factory=threading.Lock,
    )


def start_task(
    chunks: Iterable[dict], console: Console,
) -> TaskState:
    """Spawn daemon thread to stream chunks."""
    state = TaskState()
    state.status = "running"
    t = threading.Thread(
        target=_run_stream,
        args=(chunks, console, state),
        daemon=True,
    )
    t.start()
    return state


def _run_stream(
    chunks: Iterable[dict], console: Console, state: TaskState,
) -> None:
    """Stream chunks in background thread."""
    try:
        for chunk in chunks:
            if state.cancel_event.is_set():
                with state.lock:
                    state.status = "cancelled"
                return
            _process_chunk(state, console, chunk)
            with state.lock:
                state.chunks_received += 1
        with state.lock:
            state.status = "done"
    except Exception as e:
        with state.lock:
            state.error = str(e)
            state.status = "done"


def _process_chunk(
    state: TaskState, console: Console, chunk: dict,
) -> None:
    """Update state and stream live feedback."""
    ct = chunk.get("type", "")
    if ct == "routing":
        with state.lock:
            state.model = chunk.get("model", "")
        console.print(f"  [dim]{state.model}[/dim]")
    elif ct == "tool_use":
        label = _format_tool_use(chunk.get("tool", ""), chunk.get("input", {}))
        with state.lock:
            state.tool_events.append(label)
        console.print(f"  [dim cyan]> {label}[/dim cyan]")
    elif ct in ("text", "result"):
        with state.lock:
            state.content += chunk.get("content", "")
    elif ct == "agent_status":
        with state.lock:
            state.phase = chunk.get("status", "")
        console.print(f"  [dim]{state.phase}[/dim]")
    elif ct == "error":
        with state.lock:
            state.error = chunk.get("content", "")


def cancel_task(state: TaskState) -> bool:
    """Cancel a running task. Returns True if was running."""
    if state.status != "running":
        return False
    state.cancel_event.set()
    return True


def get_status(state: TaskState) -> dict:
    """Thread-safe snapshot of task state."""
    with state.lock:
        return {
            "status": state.status,
            "chunks": state.chunks_received,
            "model": state.model,
            "tools": len(state.tool_events),
            "has_error": bool(state.error),
            "phase": state.phase,
        }


def is_active(state: TaskState) -> bool:
    """True if task is currently running."""
    return state.status == "running"


def collect_result(state: TaskState) -> dict:
    """Return final result data from completed task."""
    with state.lock:
        return {
            "tool_events": list(state.tool_events),
            "content": state.content,
            "error": state.error,
        }
