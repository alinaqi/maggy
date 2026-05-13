"""Interactive chat REPL for Maggy CLI with model routing."""
from __future__ import annotations

import readline  # noqa: F401 — enables arrow key history
import select
import sys

from rich.console import Console

from maggy.cli_bg_task import (
    TaskState,
    collect_result,
    is_active,
    start_task,
)
from maggy.cli_context import gather_cli_context
from maggy.cli_repl_cmds import SessionState, dispatch
from maggy.cli_stream import stream_chunks
from maggy.cli_welcome import render_welcome

console = Console()

EXIT_WORDS = frozenset({"exit", "bye", "quit", "/exit", "/bye"})
_PROMPT = "\033[1;36m>\033[0m "  # bold cyan ">"


def run_chat(
    client, project: str, project_path: str,
    routed: bool = True,
) -> None:
    context = gather_cli_context(project_path)
    session = _find_or_create(client, project, project_path, context)
    sid = session.get("id", "?")
    wd = session.get("working_dir", project_path)
    render_welcome(project, session, client)
    state = SessionState(session_id=sid, working_dir=wd)
    state.cli_context = context
    _repl_loop(client, state, routed)
    console.print("[dim]Session saved. Bye.[/dim]")


def _find_or_create(
    client, project: str, project_path: str,
    context: str = "",
) -> dict:
    """Resume session by working_dir or create new."""
    for s in client.chat_sessions():
        if s.get("working_dir") == project_path:
            return s
    return client.chat_create(
        project, project_path, history_context=context,
    )


def _read_input(prompt: str) -> str | None:
    """Read input with readline history support."""
    try:
        return input(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        return None


def _repl_loop(
    client, state: SessionState, routed: bool,
) -> None:
    blast_override: int | None = None
    while True:
        stripped = _read_input(_PROMPT)
        if stripped is None:
            console.print()
            break
        if not stripped:
            continue
        if stripped == "/quit" or stripped.lower() in EXIT_WORDS:
            break
        if stripped == "/clear":
            console.clear()
            continue
        if stripped.startswith("/blast"):
            blast_override = _parse_blast(stripped)
            continue
        if stripped.startswith("/screenshot"):
            _handle_screenshot(stripped)
            continue
        if dispatch(stripped, client, state):
            continue
        msg = _with_context(stripped, state)
        bg = _send_message(
            client, state, msg, routed, blast_override,
        )
        blast_override = None
        if bg:
            _bg_loop(client, state, bg)


def _bg_loop(
    client, state: SessionState, bg: TaskState,
) -> None:
    """Accept commands while background task runs."""
    console.print("[dim]Task running. /status or /cancel[/dim]")
    while is_active(bg):
        ready = select.select([sys.stdin], [], [], 0.3)[0]
        if not ready:
            continue
        try:
            text = sys.stdin.readline().strip()
        except (KeyboardInterrupt, EOFError):
            from maggy.cli_bg_task import cancel_task
            cancel_task(bg)
            break
        if text and dispatch(text, client, state):
            continue
    _finish_bg(state, bg)


def _finish_bg(state: SessionState, bg: TaskState) -> None:
    """Display result from completed background task."""
    from rich.markdown import Markdown
    result = collect_result(bg)
    state.last_tool_events = result.get("tool_events", [])
    content = result.get("content", "")
    if content:
        console.print(Markdown(content))
    error = result.get("error", "")
    if error:
        console.print(f"[red]Error:[/red] {error}")
    state.bg_task = None


def _with_context(msg: str, state: SessionState) -> str:
    """Prepend CLI context to first message only."""
    ctx = getattr(state, "cli_context", "")
    if not ctx:
        return msg
    state.cli_context = ""
    return f"[Context]\n{ctx}\n[/Context]\n\n{msg}"


def _send_message(
    client, state: SessionState, message: str,
    routed: bool, blast: int | None,
) -> TaskState | None:
    """Send message, stream or start background task."""
    if routed:
        chunks = client.chat_send_routed(
            state.session_id, message,
            blast=blast,
            allowed_models=state.allowed_models or None,
        )
        bg = start_task(chunks, console)
        state.bg_task = bg
        return bg
    chunks = client.chat_send_stream(
        state.session_id, message,
    )
    result = stream_chunks(chunks, console)
    state.last_tool_events = result.get("tool_events", [])
    return None


def _parse_blast(text: str) -> int | None:
    parts = text.split()
    if len(parts) >= 2:
        try:
            val = max(1, min(10, int(parts[1])))
            console.print(f"[dim]Blast: {val}[/dim]")
            return val
        except ValueError:
            pass
    console.print("[dim]Usage: /blast N (1-10)[/dim]")
    return None


def _handle_screenshot(text: str) -> None:
    """Send image to vision model for analysis."""
    from maggy.services.vision import analyze_image
    parts = text.split(None, 2)
    if len(parts) < 2:
        console.print("[dim]Usage: /screenshot <path> [prompt][/dim]")
        return
    path = parts[1]
    prompt = parts[2] if len(parts) > 2 else None
    console.print(f"[dim]Analyzing {path}...[/dim]")
    stream_chunks(analyze_image(path, prompt), console)
