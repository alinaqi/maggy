"""Kimi CLI history parser — reads ~/.kimi/ local state."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from maggy.history.models import SessionEntry

from .base import HistoryParser

logger = logging.getLogger(__name__)


def _float_to_iso(ts: float) -> str:
    """Convert Unix float seconds to ISO-8601."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.isoformat()


def _read_jsonl(path: Path) -> list[dict]:
    """Read JSONL file, skip bad lines."""
    if not path.exists():
        return []
    results: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return results


def _extract_topics(texts: list[str]) -> list[str]:
    """Extract keyword topics from texts."""
    from collections import Counter
    words: list[str] = []
    for text in texts:
        for w in text.lower().split():
            if len(w) > 3 and w.isalpha():
                words.append(w)
    counts = Counter(words)
    return [w for w, _ in counts.most_common(5)]


class KimiHistoryParser(HistoryParser):
    """Parse Moonshot Kimi CLI session history."""

    provider = "kimi"

    def __init__(self, kimi_dir: Path | None = None):
        self._dir = kimi_dir or (
            Path.home() / ".kimi"
        )

    def is_available(self) -> bool:
        sessions = self._dir / "sessions"
        return sessions.exists() and sessions.is_dir()

    def session_count(self) -> int:
        return len(self._find_session_dirs())

    def parse_sessions(
        self, limit: int = 500,
    ) -> list[SessionEntry]:
        dirs = self._find_session_dirs()
        sessions: list[SessionEntry] = []
        for d in dirs[:limit]:
            entry = self._parse_session_dir(d)
            if entry:
                sessions.append(entry)
        return sessions

    def _find_session_dirs(self) -> list[Path]:
        """Find all session UUID directories."""
        sessions_root = self._dir / "sessions"
        if not sessions_root.exists():
            return []
        dirs: list[Path] = []
        for hash_dir in sessions_root.iterdir():
            if not hash_dir.is_dir():
                continue
            for uuid_dir in hash_dir.iterdir():
                if not uuid_dir.is_dir():
                    continue
                ctx = uuid_dir / "context.jsonl"
                if ctx.exists():
                    dirs.append(uuid_dir)
        return dirs

    def _resolve_project(self, session_id: str) -> str:
        """Read project path from kimi.json work_dirs."""
        config_path = self._dir / "kimi.json"
        if not config_path.exists():
            return ""
        try:
            data = json.loads(config_path.read_text())
            dirs = data.get("work_dirs", [])
            if isinstance(dirs, list):
                for entry in dirs:
                    if isinstance(entry, dict) and entry.get("last_session_id") == session_id:
                        path = entry.get("path", "")
                        if path:
                            return str(Path(path).expanduser().resolve())
            elif isinstance(dirs, dict):
                path = dirs.get(session_id, "")
                if path:
                    return str(Path(path).expanduser().resolve())
        except (json.JSONDecodeError, OSError):
            pass
        return ""

    def _parse_session_dir(
        self, session_dir: Path,
    ) -> SessionEntry | None:
        context = _read_jsonl(
            session_dir / "context.jsonl"
        )
        if not context:
            return None

        user_msgs = [
            e for e in context
            if e.get("role") == "user"
        ]
        prompts = []
        for e in user_msgs:
            c = e.get("content", "")
            if isinstance(c, str):
                prompts.append(c)
            elif isinstance(c, list):
                prompts.append(str(c[0]) if c else "")
        summary = prompts[0][:100] if prompts else ""

        wire = self._parse_wire(session_dir)

        return SessionEntry(
            session_id=session_dir.name,
            provider="kimi",
            project=self._resolve_project(session_dir.name),
            started_at=wire.get("started", ""),
            ended_at=wire.get("ended", ""),
            prompt_count=len(user_msgs),
            tool_use_count=wire.get("steps", 0),
            models_used=[],
            topics=_extract_topics(prompts),
            summary=summary,
        )

    def _parse_wire(self, session_dir: Path) -> dict:
        """Extract timestamps and step counts from wire."""
        entries = _read_jsonl(
            session_dir / "wire.jsonl"
        )
        if not entries:
            return {}

        timestamps: list[float] = []
        steps = 0
        for e in entries:
            ts = e.get("timestamp")
            if isinstance(ts, (int, float)):
                timestamps.append(float(ts))
            msg_str = e.get("message", "")
            if "StepBegin" in str(msg_str):
                steps += 1

        result: dict = {"steps": steps}
        if timestamps:
            result["started"] = _float_to_iso(
                min(timestamps)
            )
            result["ended"] = _float_to_iso(
                max(timestamps)
            )
        return result
