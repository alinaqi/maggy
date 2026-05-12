"""Interactive chat REPL for Maggy CLI with model routing."""
from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.prompt import Prompt

from maggy.cli_repl_cmds import SessionState, dispatch
from maggy.cli_stream import stream_chunks
from maggy.cli_welcome import render_welcome
from maggy.services.session_detect import detect_all

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
    session = _find_or_create(client, project, project_path)
    sid = session.get("id", "?")
    wd = session.get("working_dir", project_path)
    render_welcome(project, session, client)
    _show_resume_info(client, sid, wd)
    state = SessionState(session_id=sid, working_dir=wd)
    _repl_loop(client, state, routed)
    console.print("[dim]Session saved. Bye.[/dim]")


def _find_or_create(
    client, project: str, project_path: str,
) -> dict:
    """Resume session by working_dir or create new."""
    for s in client.chat_sessions():
        if s.get("working_dir") == project_path:
            return s
    return client.chat_create(project, project_path)


def _show_resume_info(client, sid: str, wd: str) -> None:
    detected = detect_all(wd)
    if detected.sessions:
        parts = [f"{s.cli}({s.session_id[:8]})" for s in detected.sessions]
        console.print(f"[dim]Prior: {', '.join(parts)}[/dim]")
    for msg in client.chat_history(sid).get("messages", [])[-3:]:
        role = msg.get("role", "?")
        text = msg.get("content", "")[:120]
        tag = "[cyan]You[/cyan]" if role == "user" else "[green]Maggy[/green]"
        console.print(f"  {tag}: {text}")


def _repl_loop(client, state: SessionState, routed: bool) -> None:
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
        if stripped == "/history":
            _show_history(client, state.session_id)
            continue
        if stripped == "/sessions":
            _show_sessions(client)
            continue
        if stripped == "/clear":
            console.clear()
            continue
        if stripped.startswith("/monitor"):
            data = _call_safe(client.monitor_status)
            console.print(f"[dim]Monitors: {data.get('active', 0)} active[/dim]")
            continue
        if stripped.startswith("/screenshot"):
            _handle_screenshot(stripped)
            continue
        if stripped.startswith("/blast"):
            blast_override = _parse_blast(stripped)
            continue
        if dispatch(stripped, client, state):
            continue
        if routed:
            chunks = client.chat_send_routed(
                state.session_id, stripped,
                blast=blast_override,
                allowed_models=state.allowed_models or None,
            )
        else:
            chunks = client.chat_send_stream(
                state.session_id, stripped,
            )
        stream_chunks(chunks, console)
        blast_override = None


def _parse_blast(text: str) -> int | None:
    parts = text.split()
    if len(parts) >= 2:
        try:
            val = max(1, min(10, int(parts[1])))
            console.print(f"[dim]Blast override: {val}[/dim]")
            return val
        except ValueError:
            pass
    console.print("[dim]Usage: /blast N (1-10)[/dim]")
    return None


def _call_safe(fn, default=None):
    try:
        return fn()
    except (Exception, SystemExit):
        return default if default is not None else {}


def _handle_screenshot(text: str) -> None:
    """Send image to Qwen3-VL for analysis."""
    from maggy.services.vision import analyze_image
    parts = text.split(None, 2)
    if len(parts) < 2:
        console.print("[dim]Usage: /screenshot <path> [prompt][/dim]")
        return
    path = parts[1]
    prompt = parts[2] if len(parts) > 2 else None
    console.print(f"[dim]Analyzing {path}...[/dim]")
    stream_chunks(analyze_image(path, prompt), console)


def _show_history(client, session_id: str) -> None:
    msgs = client.chat_history(session_id).get("messages", [])
    if not msgs:
        console.print("[dim]No messages yet.[/dim]")
        return
    for msg in msgs:
        role, content = msg.get("role", "?"), msg.get("content", "")
        tag = "[cyan]You[/cyan]" if role == "user" else "[green]Maggy[/green]"
        console.print(f"  {tag}: {content[:120]}")


def _show_sessions(client) -> None:
    sessions = client.chat_sessions()
    if not sessions:
        console.print("[dim]No chat sessions.[/dim]")
        return
    for s in sessions:
        sid = s.get("id", "?")[:8]
        proj = s.get("project_key", "?")
        n = s.get("messages", 0)
        console.print(f"  [bold]{sid}[/bold] {proj} ({n} msgs)")
