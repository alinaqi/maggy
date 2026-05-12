"""Rich streaming display — spinner, jokes, model label."""
from __future__ import annotations

import random
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.rule import Rule
from rich.spinner import Spinner
from rich.text import Text

_QUOTA_MARKERS = ("rate_limit", "quota", "exceeded", "429")

_JOKES = [
    ("Knock knock.", "Who's there?", "Git.", "Git who?",
     "Git commit or git out!"),
    ("Knock knock.", "Who's there?", "Cache.", "Cache who?",
     "Cache me outside, how bout dat?"),
    ("Knock knock.", "Who's there?", "Null.", "Null who?",
     "Exactly."),
    ("Knock knock.", "Who's there?", "Recursion.",
     "Recursion who?", "Knock knock."),
    ("Knock knock.", "Who's there?", "Sudo.", "Sudo who?",
     "Sudo make me a sandwich!"),
    ("Knock knock.", "Who's there?", "404.", "404 who?",
     "Page not found. Try again."),
    ("Knock knock.", "Who's there?", "SSH.", "SSH who?",
     "SSH! I'm debugging!"),
    ("Knock knock.", "Who's there?", "Vim.", "Vim who?",
     "Vim trying to exit for hours!"),
    ("Knock knock.", "Who's there?", "Merge.", "Merge who?",
     "Merge conflict! Good luck."),
    ("Knock knock.", "Who's there?", "AI.", "AI who?",
     "AI'll handle this, don't worry!"),
    ("Knock knock.", "Who's there?", "Regex.", "Regex who?",
     "Regex-ter your patterns carefully!"),
    ("Knock knock.", "Who's there?", "REST.", "REST who?",
     "REST assured, I'm working on it!"),
    ("Knock knock.", "Who's there?", "Deploy.", "Deploy who?",
     "Deploy the code before Friday!"),
    ("Knock knock.", "Who's there?", "CI.", "CI who?",
     "CI you later, pipeline's running!"),
    ("Knock knock.", "Who's there?", "Port.", "Port who?",
     "Port 8080 is already in use!"),
]


@dataclass
class _StreamState:
    """Mutable state shared between stream loop and joke thread.

    Threading: joke_line is written by the joke thread; all other
    mutable fields are written only by the main thread.  The lock
    protects every read/write so the Live auto-refresh thread
    (which calls __rich__) always sees consistent snapshots.
    """

    console: Console
    model_label: str = ""
    content: str = ""
    joke_line: str = ""
    error: str = ""
    stop: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __rich__(self) -> Group:
        """Called by Live on every auto-refresh tick."""
        return _build_display(self)


def _cycle_jokes(state: _StreamState) -> None:
    """Rotate joke lines in a background thread."""
    order = list(range(len(_JOKES)))
    random.shuffle(order)
    idx = 0
    while not state.stop.is_set():
        for line in _JOKES[order[idx % len(order)]]:
            if state.stop.is_set():
                return
            with state.lock:
                state.joke_line = line
            state.stop.wait(1.5)
        idx = (idx + 1) % len(order)


def _build_display(state: _StreamState) -> Group:
    """Compose spinner/content + model label + joke line."""
    with state.lock:
        label = state.model_label
        content = state.content
        jl = state.joke_line
    parts: list = []
    if label:
        parts.append(Rule(f" {label} ", style="dim"))
    if content:
        parts.append(Markdown(content))
    else:
        parts.append(Spinner("dots", text="Thinking\u2026"))
    if jl:
        parts.append(Text(f"  {jl}", style="dim italic"))
    return Group(*parts)


def _handle_chunk(state: _StreamState, chunk: dict) -> bool:
    """Process one SSE chunk. Returns False on 'done'."""
    ct = chunk.get("type", "")
    if ct == "routing":
        model = chunk.get("model", "?")
        blast = chunk.get("blast", "?")
        with state.lock:
            state.model_label = f"Working with {model} \u00b7 blast {blast}"
    elif ct == "queued":
        with state.lock:
            state.model_label = f"Queued (position {chunk.get('position', '?')})"
    elif ct in ("warning", "agent_status"):
        msg = chunk.get("content", chunk.get("status", ""))
        state.console.print(f"[dim]{msg}[/dim]")
    elif ct in ("text", "result"):
        with state.lock:
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
    if any(m in state.error.lower() for m in _QUOTA_MARKERS):
        from maggy.services.account_guide import render_switch_guide
        render_switch_guide("anthropic")


def stream_chunks(
    chunks: Iterable[dict], console: Console,
) -> None:
    """Stream SSE chunks with jokes and model label."""
    state = _StreamState(console=console)
    t = threading.Thread(
        target=_cycle_jokes, args=(state,), daemon=True,
    )
    t.start()
    try:
        with Live(state, console=console, refresh_per_second=8) as live:
            for chunk in chunks:
                if not _handle_chunk(state, chunk):
                    break
            if state.content:
                live.update(Markdown(state.content))
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted[/dim]")
    except Exception as e:
        state.error = str(e)
    finally:
        state.stop.set()
    _show_error(state)
