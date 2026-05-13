"""Interactive chat REPL for Maggy CLI with model routing."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from maggy.cli_context import gather_cli_context
from maggy.cli_repl_cmds import SessionState, dispatch
from maggy.cli_stream import stream_chunks
from maggy.cli_welcome import render_welcome

console = Console()

EXIT_WORDS = frozenset({"exit", "bye", "quit", "/exit", "/bye"})


def cwd_project() -> tuple[str, str]:
    """Return (folder_name, resolved_path) for cwd."""
    p = Path.cwd().resolve()
    return p.name, str(p)


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


def _repl_loop(
    client, state: SessionState, routed: bool,
) -> None:
    blast_override: int | None = None
    while True:
        try:
            text = Prompt.ask("[bold cyan]>[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            console.print()
            break
        stripped = text.strip()
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
        _send_message(client, state, msg, routed, blast_override)
        blast_override = None


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
) -> None:
    """Send message and stream response."""
    if routed:
        chunks = client.chat_send_routed(
            state.session_id, message,
            blast=blast,
            allowed_models=state.allowed_models or None,
        )
    else:
        chunks = client.chat_send_stream(
            state.session_id, message,
        )
    result = stream_chunks(chunks, console)
    state.last_tool_events = result.get("tool_events", [])


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
