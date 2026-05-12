"""CLI context gathering from Claude/Codex/Kimi history."""
from __future__ import annotations

from pathlib import Path


def gather_cli_context(working_dir: str) -> str:
    """Gather recent activity from Claude/Codex/Kimi."""
    try:
        from maggy.history.service import HistoryService
        svc = HistoryService()
        providers = svc.available_providers()
        if not providers:
            return ""
        sessions = svc.get_sessions()
        return _format_sessions(sessions, working_dir)
    except Exception:
        return ""


def _format_sessions(
    sessions: list[dict], working_dir: str,
) -> str:
    """Format recent sessions as brief context string."""
    target = working_dir.rstrip("/")
    recent = [
        s for s in sessions
        if _matches_project(s, target)
    ][:10]
    if not recent:
        return ""
    lines = []
    for s in recent:
        provider = s.get("provider", "?")
        prompts = s.get("prompt_count", 0)
        summary = s.get("summary", "")[:120]
        started = s.get("started_at", "")[:16]
        line = f"- {provider}: {prompts} prompts"
        if started:
            line += f" ({started})"
        if summary:
            line += f" — {summary}"
        lines.append(line)
    return "Recent CLI activity:\n" + "\n".join(lines)


def _matches_project(
    session: dict, target: str,
) -> bool:
    """Check if session matches project directory."""
    proj = session.get("project", "")
    return (
        proj == target
        or proj.rstrip("/") == target
        or Path(target).name in proj
    )
