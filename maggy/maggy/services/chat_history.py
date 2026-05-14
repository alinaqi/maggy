"""Load conversation history from Claude Code sessions.

Reads ~/.claude/projects/<slug>/<sessionId>.jsonl to extract
user/assistant message pairs for display in Maggy dashboard.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_CLAUDE_DIR = Path.home() / ".claude" / "projects"
_MAX_MESSAGES = 50
_MAX_CONTENT_LEN = 2000
_TAIL_BYTES = 512 * 1024  # read last 512KB of large files


def load_claude_history(
    working_dir: str, session_id: str = "",
) -> list[dict]:
    """Load messages from the most recent Claude session.

    Tries exact session_id first, then falls back to the
    most recent JSONL in the project directory. Also walks
    up to parent directories if no exact match found.
    """
    slug = _path_to_slug(working_dir)
    if not slug:
        return []
    if session_id:
        jsonl = _find_jsonl(slug, session_id, working_dir)
        if jsonl:
            return _parse_jsonl(jsonl)
    return _load_most_recent(slug, working_dir)


def _path_to_slug(path: str) -> str:
    """Convert directory path to Claude's slug format."""
    return path.rstrip("/").replace("/", "-")


def _find_jsonl(
    slug: str, session_id: str, working_dir: str,
) -> Path | None:
    """Find session JSONL, trying slug then parent slugs."""
    target = _CLAUDE_DIR / slug / f"{session_id}.jsonl"
    if target.exists():
        return target
    p = Path(working_dir).parent
    home = str(Path.home())
    while str(p) != home and len(p.parts) > 2:
        parent_slug = _path_to_slug(str(p))
        target = _CLAUDE_DIR / parent_slug / f"{session_id}.jsonl"
        if target.exists():
            return target
        p = p.parent
    return None


def _load_most_recent(
    slug: str, working_dir: str,
) -> list[dict]:
    """Load the most recent JSONL from project dir."""
    jsonl = _newest_jsonl(_CLAUDE_DIR / slug)
    if jsonl:
        return _parse_jsonl(jsonl)
    p = Path(working_dir).parent
    home = str(Path.home())
    while str(p) != home and len(p.parts) > 2:
        parent_slug = _path_to_slug(str(p))
        jsonl = _newest_jsonl(_CLAUDE_DIR / parent_slug)
        if jsonl:
            return _parse_jsonl(jsonl)
        p = p.parent
    return []


def _newest_jsonl(directory: Path) -> Path | None:
    """Find the most recently modified JSONL in a dir."""
    if not directory.exists():
        return None
    jsonls = [
        f for f in directory.glob("*.jsonl")
        if f.stat().st_size > 1000
    ]
    if not jsonls:
        return None
    return max(jsonls, key=lambda f: f.stat().st_mtime)


def _read_lines(path: Path) -> list[str]:
    """Read JSONL lines, tail-reading for large files."""
    size = path.stat().st_size
    if size <= _TAIL_BYTES:
        try:
            return path.read_text().splitlines()
        except OSError:
            return []
    # Large file: read only the last chunk
    try:
        with open(path, "rb") as f:
            f.seek(max(0, size - _TAIL_BYTES))
            chunk = f.read().decode("utf-8", errors="replace")
        lines = chunk.splitlines()
        if lines:
            lines = lines[1:]  # drop partial first line
        return lines
    except OSError:
        return []


def _parse_jsonl(path: Path) -> list[dict]:
    """Extract user/assistant messages from JSONL."""
    messages: list[dict] = []
    lines = _read_lines(path)
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        msg_type = entry.get("type", "")
        if msg_type not in ("user", "assistant"):
            continue
        msg = entry.get("message", {})
        text = _extract_text(msg)
        if not text or len(text) < 3:
            continue
        if _is_system_noise(text):
            continue
        if len(text) > _MAX_CONTENT_LEN:
            text = text[:_MAX_CONTENT_LEN] + "..."
        messages.append({
            "role": msg_type,
            "content": text,
            "timestamp": entry.get("timestamp", ""),
        })
    return messages[-_MAX_MESSAGES:]


def _extract_text(msg: dict) -> str:
    """Pull plain text from message content."""
    content = msg.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts).strip()
    return ""


_CMD_RE = re.compile(
    r"<(?:command-|local-command|task-notification)"
)


def _is_system_noise(text: str) -> bool:
    """Filter out system/command messages."""
    stripped = text.strip()
    return bool(_CMD_RE.match(stripped))
