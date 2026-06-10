"""CLI session refresh — pull and summarize recent CLI conversations."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SessionDigest:
    """Summary of a CLI conversation session."""

    session_id: str
    cli: str
    project: str
    project_path: str
    last_prompt: str
    timestamp: str
    turns: list[dict] = field(default_factory=list)


class RefreshService:
    def __init__(
        self,
        claude_dir: Path | None = None,
        codex_dir: Path | None = None,
    ) -> None:
        home = Path.home()
        self._claude_dir = claude_dir or (home / ".claude")
        self._codex_dir = codex_dir or (home / ".codex")

    def refresh(
        self, limit: int = 3, project_path: str | None = None,
    ) -> list[SessionDigest]:
        sessions = _find_recent_sessions(
            self._claude_dir, limit=limit,
            project_path=project_path,
        )
        digests: list[SessionDigest] = []
        for s in sessions:
            slug = _path_to_slug(s["project_path"])
            turns = _extract_conversation(
                self._claude_dir, slug, s["session_id"],
                max_turns=20,
            )
            digests.append(SessionDigest(
                session_id=s["session_id"],
                cli="claude",
                project=s["project"],
                project_path=s["project_path"],
                last_prompt=s["last_prompt"],
                timestamp=s["timestamp"],
                turns=turns,
            ))
        return digests


def _find_recent_sessions(
    claude_dir: Path,
    limit: int = 5,
    project_path: str | None = None,
) -> list[dict]:
    path = claude_dir / "history.jsonl"
    if not path.exists():
        return []
    seen: dict[str, dict] = {}
    try:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            sid = entry.get("sessionId", "")
            if not sid:
                continue
            proj_path = entry.get("project", "")
            if project_path and not _path_matches(proj_path, project_path):
                continue
            seen[sid] = {
                "session_id": sid,
                "last_prompt": entry.get("display", ""),
                "project_path": proj_path,
                "project": Path(proj_path).name if proj_path else "",
                "timestamp": entry.get("timestamp", ""),
            }
    except OSError:
        return []
    sessions = list(seen.values())
    sessions.sort(key=lambda s: s["timestamp"], reverse=True)
    return sessions[:limit]


def _extract_conversation(
    claude_dir: Path, project_slug: str,
    session_id: str, max_turns: int = 20,
) -> list[dict]:
    proj_dir = claude_dir / "projects" / project_slug
    path = proj_dir / f"{session_id}.jsonl"
    if not path.exists():
        return []
    turns: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = entry.get("type", "")
            if t not in ("user", "assistant"):
                continue
            text = _extract_text(entry)
            if text:
                turns.append({"role": t, "text": text})
    except OSError:
        return []
    return turns[-max_turns:]


def _extract_text(entry: dict) -> str:
    msg = entry.get("message", {})
    if not isinstance(msg, dict):
        return ""
    content = msg.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return " ".join(parts)
    return ""


def _path_matches(session_path: str, filter_path: str) -> bool:
    s = session_path.rstrip("/")
    f = filter_path.rstrip("/")
    return s == f or s.startswith(f + "/") or f.startswith(s + "/")


def _path_to_slug(project_path: str) -> str:
    return project_path.replace("/", "-")


def format_digest(digest: SessionDigest) -> str:
    lines = [
        f"**{digest.cli.upper()}** — {digest.project}",
        f"Session: `{digest.session_id[:8]}…`",
        "",
    ]
    for turn in digest.turns[-10:]:
        role = "You" if turn["role"] == "user" else "AI"
        text = turn["text"][:200]
        lines.append(f"**{role}:** {text}")
    return "\n".join(lines)
