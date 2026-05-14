"""Chat context builder — resolves history and session IDs.

Handles the three context gaps:
1. Path-based history matching (not just project name)
2. Recent prompt injection from activity data
3. Claude session_id lookup for true --resume
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def build_project_context(
    history, working_dir: str,
    project_key: str, recent_prompts: list[dict],
) -> str:
    """Build full context string for a project."""
    parts = []
    hist = _match_history(history, working_dir, project_key)
    if hist:
        parts.append(hist)
    prompts = _format_recent_prompts(recent_prompts, project_key)
    if prompts:
        parts.append(prompts)
    return "\n\n".join(parts)


def _match_history(
    history, working_dir: str, project_key: str,
) -> str:
    """Match history using report data (path-aware)."""
    if not history:
        return ""
    report = history.get_report()
    if report:
        return _match_from_report(
            report, working_dir, project_key,
        )
    return ""


def _match_from_report(
    report: dict, working_dir: str, project_key: str,
) -> str:
    """Match project in the aggregated history report."""
    projects = report.get("projects", [])
    if not projects:
        return ""
    candidates = _path_candidates(working_dir, project_key)
    matched = [
        p for p in projects
        if p.get("project", "") in candidates
    ]
    if not matched:
        return ""
    lines = []
    for p in matched:
        sessions = p.get("total_sessions", 0)
        prompts = p.get("total_prompts", 0)
        providers = ", ".join(p.get("providers_used", []))
        topics = ", ".join(p.get("top_topics", [])[:5])
        line = f"- {sessions} sessions, {prompts} prompts"
        if providers:
            line += f" ({providers})"
        if topics:
            line += f", topics: {topics}"
        lines.append(line)
    return (
        f"Project history ({len(matched)} entries):\n"
        + "\n".join(lines)
    )


_SKIP_DIRS = {
    "Users", "home", "Documents", "var", "tmp", "opt",
    "usr", "Library", "Applications",
}


def _path_candidates(
    working_dir: str, project_key: str,
) -> set[str]:
    """Generate candidate project names from path."""
    candidates = {project_key}
    if working_dir:
        parts = Path(working_dir).parts
        for part in parts:
            if (part and part != "/"
                    and len(part) > 2
                    and part not in _SKIP_DIRS):
                candidates.add(part)
    return candidates


def _format_recent_prompts(
    recent_prompts: list[dict], project_key: str,
) -> str:
    """Format recent prompts for this project."""
    matched = [
        p for p in recent_prompts
        if p.get("project", "") == project_key
    ][:5]
    if not matched:
        return ""
    lines = []
    for p in matched:
        text = p.get("text", "")[:120]
        ts = p.get("timestamp", "")[:10]
        lines.append(f"- [{ts}] {text}")
    return "Recent prompts:\n" + "\n".join(lines)


def resolve_claude_session_id(
    working_dir: str,
) -> str:
    """Find the latest Claude session_id for a project.

    Reads ~/.claude/history.jsonl to find the most recent
    sessionId used in this working directory. Falls back
    to parent directories (e.g. /protaige matches
    /protaige/protaige-mvp-backend).
    """
    entries = _load_history_entries()
    if not entries:
        return ""
    target = working_dir.rstrip("/")
    sid = _match_session_exact(entries, target)
    if sid:
        return sid
    return _match_session_parent(entries, target)


def _load_history_entries() -> list[dict]:
    """Load parsed entries from history.jsonl."""
    path = Path.home() / ".claude" / "history.jsonl"
    if not path.exists():
        return []
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return []
    entries = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return entries


def _match_session_exact(
    entries: list[dict], target: str,
) -> str:
    """Exact path match against history entries."""
    for entry in entries:
        project = entry.get("project", "").rstrip("/")
        if project == target:
            sid = entry.get("sessionId", "")
            if sid:
                return sid
    return ""


def _match_session_parent(
    entries: list[dict], target: str,
) -> str:
    """Parent-path fallback: find session from ancestor dir."""
    parents = _parent_paths(target)
    for parent in parents:
        for entry in entries:
            project = entry.get("project", "").rstrip("/")
            if project == parent:
                sid = entry.get("sessionId", "")
                if sid:
                    return sid
    return ""


def _parent_paths(path: str) -> list[str]:
    """Walk up from path, skip generic system dirs."""
    skip = {"/", "/Users", "/home", str(Path.home())}
    result = []
    p = Path(path).parent
    while str(p) not in skip and len(p.parts) > 2:
        result.append(str(p))
        p = p.parent
    return result
