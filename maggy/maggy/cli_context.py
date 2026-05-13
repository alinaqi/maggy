"""CLI context gathering from Claude/Codex/Kimi history."""
from __future__ import annotations

from pathlib import Path


def cwd_project() -> tuple[str, str]:
    """Return (folder_name, resolved_path) for cwd."""
    p = Path.cwd().resolve()
    return p.name, str(p)


def gather_cli_context(working_dir: str) -> str:
    """Gather verified context + CLI history."""
    parts: list[str] = []
    parts.append(_gather_verified(working_dir))
    parts.append(_gather_history(working_dir))
    return "\n\n".join(p for p in parts if p)


def _gather_verified(working_dir: str) -> str:
    """Get verified git state."""
    try:
        from maggy.services.verified_context import (
            format_verified,
            gather_verified,
        )
        ctx = gather_verified(working_dir)
        return format_verified(ctx)
    except Exception:
        return ""


def _gather_history(working_dir: str) -> str:
    """Gather history from Claude/Codex/Kimi."""
    try:
        from maggy.history.service import HistoryService
        svc = HistoryService()
        providers = svc.available_providers()
        if not providers:
            return _fallback_detect(working_dir)
        sessions = svc.get_sessions()
        result = _format_sessions(sessions, working_dir)
        if result:
            return result
        return _fallback_detect(working_dir)
    except Exception:
        return _fallback_detect(working_dir)


def _fallback_detect(working_dir: str) -> str:
    """Use session_detect for live file detection."""
    try:
        from maggy.services.session_detect import detect_all
        active = detect_all(working_dir)
        if not active:
            return ""
        lines = []
        for s in active[:5]:
            provider = s.get("provider", "?")
            pid = s.get("pid", "")
            line = f"- {provider}: active"
            if pid:
                line += f" (pid {pid})"
            lines.append(line)
        return "Active CLI sessions:\n" + "\n".join(lines)
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
    if not proj:
        return False
    t = target.rstrip("/")
    p = proj.rstrip("/")
    return p == t
