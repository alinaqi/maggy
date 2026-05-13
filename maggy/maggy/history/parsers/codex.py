"""Codex CLI history parser — reads ~/.codex/ local state."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from maggy.history.models import SessionEntry

from .base import HistoryParser

logger = logging.getLogger(__name__)


def _seconds_to_iso(ts: int | float) -> str:
    """Convert Unix seconds to ISO-8601."""
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
    """Extract keyword topics from prompt texts."""
    from collections import Counter
    words: list[str] = []
    for text in texts:
        for w in text.lower().split():
            if len(w) > 3 and w.isalpha():
                words.append(w)
    counts = Counter(words)
    return [w for w, _ in counts.most_common(5)]


class CodexHistoryParser(HistoryParser):
    """Parse OpenAI Codex CLI session history."""

    provider = "codex"

    def __init__(self, codex_dir: Path | None = None):
        self._dir = codex_dir or (
            Path.home() / ".codex"
        )

    def is_available(self) -> bool:
        index = self._dir / "session_index.jsonl"
        return index.exists()

    def session_count(self) -> int:
        entries = _read_jsonl(
            self._dir / "session_index.jsonl"
        )
        return len(entries)

    def parse_sessions(
        self, limit: int = 500,
    ) -> list[SessionEntry]:
        index = _read_jsonl(
            self._dir / "session_index.jsonl"
        )
        if not index:
            return []

        history = _read_jsonl(
            self._dir / "history.jsonl"
        )
        prompts_by_sid = self._group_prompts(history)

        sessions: list[SessionEntry] = []
        for entry in index[:limit]:
            sid = entry.get("id", "")
            if not sid:
                continue
            session = self._build_entry(
                entry, prompts_by_sid.get(sid, []),
            )
            sessions.append(session)
        return sessions

    def _group_prompts(
        self, history: list[dict],
    ) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for h in history:
            sid = h.get("session_id", "")
            if sid:
                grouped[sid].append(h)
        return dict(grouped)

    def _find_cwd(self, sid: str) -> str:
        """Read cwd from rollout file for session."""
        sess_dir = self._dir / "sessions"
        if not sess_dir.exists():
            return ""
        rollout = sess_dir / f"rollout-{sid}.jsonl"
        if not rollout.exists():
            return ""
        for entry in _read_jsonl(rollout):
            cwd = entry.get("cwd", "")
            if cwd:
                return str(Path(cwd).expanduser().resolve())
        return ""

    def _build_entry(
        self, index_entry: dict, prompts: list[dict],
    ) -> SessionEntry:
        sid = index_entry.get("id", "")
        thread_name = index_entry.get("thread_name", "")
        updated = index_entry.get("updated_at", "")

        timestamps = [
            p["ts"] for p in prompts if "ts" in p
        ]
        texts = [
            p.get("text", "") for p in prompts
            if p.get("text")
        ]

        started = _seconds_to_iso(min(timestamps)) if timestamps else updated
        ended = _seconds_to_iso(max(timestamps)) if timestamps else updated

        return SessionEntry(
            session_id=sid,
            provider="codex",
            project=self._find_cwd(sid),
            started_at=started,
            ended_at=ended,
            prompt_count=len(prompts),
            tool_use_count=0,
            models_used=[],
            topics=_extract_topics(texts),
            summary=thread_name or (
                texts[0][:100] if texts else ""
            ),
        )
