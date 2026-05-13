"""Claude Code history parser — reads ~/.claude/ local state."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from maggy.history.models import SessionEntry

from .base import HistoryParser

logger = logging.getLogger(__name__)


def _millis_to_iso(ms: int | float) -> str:
    """Convert Unix milliseconds to ISO-8601."""
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
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


def _extract_topics(prompts: list[str]) -> list[str]:
    """Extract keyword topics from prompt texts."""
    from collections import Counter
    words: list[str] = []
    for text in prompts:
        for w in text.lower().split():
            if len(w) > 3 and w.isalpha():
                words.append(w)
    counts = Counter(words)
    return [w for w, _ in counts.most_common(5)]


class ClaudeHistoryParser(HistoryParser):
    """Parse Claude Code session history."""

    provider = "claude"

    def __init__(self, claude_dir: Path | None = None):
        self._dir = claude_dir or (
            Path.home() / ".claude"
        )

    def is_available(self) -> bool:
        history = self._dir / "history.jsonl"
        return history.exists()

    def session_count(self) -> int:
        entries = _read_jsonl(self._dir / "history.jsonl")
        ids = {e.get("sessionId") for e in entries}
        ids.discard(None)
        return len(ids)

    def parse_sessions(
        self, limit: int = 500,
    ) -> list[SessionEntry]:
        entries = _read_jsonl(self._dir / "history.jsonl")
        if not entries:
            return []

        grouped = self._group_by_session(entries)
        sessions: list[SessionEntry] = []
        for sid, items in list(grouped.items())[:limit]:
            session = self._build_entry(sid, items)
            sessions.append(session)
        return sessions

    def _group_by_session(
        self, entries: list[dict],
    ) -> dict[str, list[dict]]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for e in entries:
            sid = e.get("sessionId")
            if sid:
                grouped[sid].append(e)
        return dict(grouped)

    def _build_entry(
        self, sid: str, items: list[dict],
    ) -> SessionEntry:
        timestamps = [
            i["timestamp"] for i in items
            if "timestamp" in i
        ]
        project = items[0].get("project", "")
        prompts = [
            i.get("display", "") for i in items
            if i.get("display")
        ]
        summary = prompts[0] if prompts else ""

        started = _millis_to_iso(min(timestamps)) if timestamps else ""
        ended = _millis_to_iso(max(timestamps)) if timestamps else ""

        # Try reading transcript for richer data
        extra = self._parse_transcript(sid, project)

        return SessionEntry(
            session_id=sid,
            provider="claude",
            project=self._slug(project),
            started_at=started,
            ended_at=ended,
            prompt_count=len(items),
            tool_use_count=extra.get("tool_uses", 0),
            models_used=extra.get("models", []),
            git_branch=extra.get("branch", ""),
            topics=_extract_topics(prompts),
            summary=summary,
        )

    def _slug(self, project_path: str) -> str:
        """Return resolved full path for matching."""
        if not project_path:
            return ""
        return str(Path(project_path).expanduser().resolve())

    def _find_transcript(
        self, sid: str, project: str,
    ) -> Path | None:
        """Locate transcript JSONL by session ID."""
        projects_dir = self._dir / "projects"
        if not projects_dir.exists():
            return None
        slug = project.replace("/", "-").lstrip("-")
        direct = projects_dir / slug / f"{sid}.jsonl"
        if direct.exists():
            return direct
        # Search all project dirs for the session
        for d in projects_dir.iterdir():
            if not d.is_dir():
                continue
            f = d / f"{sid}.jsonl"
            if f.exists():
                return f
        return None

    def _parse_transcript(
        self, sid: str, project: str,
    ) -> dict:
        """Read session transcript for models/tools/branch."""
        if not project:
            return {}
        transcript = self._find_transcript(sid, project)
        if not transcript:
            return {}

        entries = _read_jsonl(transcript)
        models: set[str] = set()
        tool_uses = 0
        branch = ""

        for e in entries:
            etype = e.get("type", "")
            if etype == "assistant":
                m = e.get("model", "")
                if m:
                    models.add(m)
                content = e.get("message", {}).get(
                    "content", []
                )
                if isinstance(content, list):
                    tool_uses += sum(
                        1 for b in content
                        if isinstance(b, dict)
                        and b.get("type") == "tool_use"
                    )
            elif etype == "user" and not branch:
                branch = e.get("gitBranch", "")

        return {
            "models": sorted(models),
            "tool_uses": tool_uses,
            "branch": branch,
        }
