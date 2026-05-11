"""Multi-CLI session detection.

Scans Claude, Kimi, Codex state directories to find
previous sessions for a given working directory.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


def _home() -> Path:
    """Testable home directory getter."""
    return Path.home()


@dataclass
class CliSessionInfo:
    """Detected session from a CLI tool."""

    cli: str
    session_id: str
    project_path: str = ""


@dataclass
class DetectedSessions:
    """Results from scanning all CLIs."""

    sessions: list[CliSessionInfo] = field(
        default_factory=list,
    )


def detect_all(working_dir: str) -> DetectedSessions:
    """Scan all CLIs for previous sessions."""
    result = DetectedSessions()
    for fn in (detect_claude, detect_kimi, detect_codex):
        try:
            info = fn(working_dir)
            if info:
                result.sessions.append(info)
        except Exception:
            continue
    return result


def detect_claude(working_dir: str) -> CliSessionInfo | None:
    """Find latest Claude session for this directory."""
    path = _home() / ".claude" / "history.jsonl"
    if not path.exists():
        return None
    target = working_dir.rstrip("/")
    for line in reversed(path.read_text().splitlines()):
        entry = _parse_json(line)
        if not entry:
            continue
        project = entry.get("project", "").rstrip("/")
        sid = entry.get("sessionId", "")
        if project == target and sid:
            return CliSessionInfo("claude", sid, target)
    return None


def detect_kimi(working_dir: str) -> CliSessionInfo | None:
    """Find latest Kimi session from kimi.json."""
    path = _home() / ".kimi" / "kimi.json"
    if not path.exists():
        return None
    data = _parse_json(path.read_text())
    if not data:
        return None
    target = working_dir.rstrip("/")
    for entry in data.get("work_dirs", []):
        entry_path = entry.get("path", "").rstrip("/")
        sid = entry.get("last_session_id")
        if entry_path == target and sid:
            return CliSessionInfo("kimi", sid, target)
    return None


def detect_codex(working_dir: str) -> CliSessionInfo | None:
    """Find latest Codex session by scanning files."""
    sess_dir = _home() / ".codex" / "sessions"
    if not sess_dir.exists():
        return None
    target = working_dir.rstrip("/")
    files = sorted(
        sess_dir.rglob("rollout-*.jsonl"), reverse=True,
    )
    for f in files[:50]:
        entry = _parse_json(_read_first_line(f))
        if not entry:
            continue
        payload = entry.get("payload", {})
        cwd = payload.get("cwd", "").rstrip("/")
        sid = payload.get("id", "")
        if cwd == target and sid:
            return CliSessionInfo("codex", sid, target)
    return None


def _parse_json(text: str) -> dict | None:
    """Safe JSON parse, returns None on failure."""
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _read_first_line(path: Path) -> str:
    """Read first line of a file safely."""
    try:
        with path.open() as f:
            return f.readline()
    except OSError:
        return ""
