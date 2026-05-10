"""SQLite store for session history data."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .models import HistoryReport, SessionEntry

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    project TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL DEFAULT '',
    prompt_count INTEGER NOT NULL DEFAULT 0,
    tool_use_count INTEGER NOT NULL DEFAULT 0,
    models_used TEXT NOT NULL DEFAULT '[]',
    git_branch TEXT NOT NULL DEFAULT '',
    topics TEXT NOT NULL DEFAULT '[]',
    summary TEXT NOT NULL DEFAULT '',
    ingested_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hsess_provider
    ON sessions(provider);
CREATE INDEX IF NOT EXISTS idx_hsess_project
    ON sessions(project);

CREATE TABLE IF NOT EXISTS history_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


@contextmanager
def _connect(path: Path) -> Iterator[sqlite3.Connection]:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class HistoryStore:
    """SQLite-backed session history storage."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        with _connect(self._db_path) as conn:
            conn.executescript(SCHEMA)

    def save_sessions(
        self, sessions: list[SessionEntry],
    ) -> None:
        """Save parsed session entries."""
        now = datetime.now(timezone.utc).isoformat()
        with _connect(self._db_path) as conn:
            for s in sessions:
                conn.execute(
                    "INSERT INTO sessions "
                    "(session_id, provider, project, "
                    "started_at, ended_at, prompt_count, "
                    "tool_use_count, models_used, "
                    "git_branch, topics, summary, "
                    "ingested_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        s.session_id, s.provider,
                        s.project, s.started_at,
                        s.ended_at, s.prompt_count,
                        s.tool_use_count,
                        json.dumps(s.models_used),
                        s.git_branch,
                        json.dumps(s.topics),
                        s.summary, now,
                    ),
                )
            conn.commit()

    def load_sessions(
        self,
        provider: str | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """Load stored session records."""
        with _connect(self._db_path) as conn:
            if provider:
                rows = conn.execute(
                    "SELECT * FROM sessions "
                    "WHERE provider = ? "
                    "ORDER BY started_at DESC "
                    "LIMIT ?",
                    (provider, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions "
                    "ORDER BY started_at DESC "
                    "LIMIT ?",
                    (limit,),
                ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def save_report(self, report: HistoryReport) -> None:
        """Save an analysis report."""
        payload = json.dumps(asdict(report))
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO history_reports "
                "(generated_at, payload) VALUES (?, ?)",
                (report.generated_at, payload),
            )
            conn.commit()

    def load_latest_report(self) -> dict | None:
        """Load the most recent report."""
        with _connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT payload FROM history_reports "
                "ORDER BY id DESC LIMIT 1",
            ).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])

    def _row_to_dict(self, r: sqlite3.Row) -> dict:
        """Convert a session row to dict."""
        return {
            "session_id": r["session_id"],
            "provider": r["provider"],
            "project": r["project"],
            "started_at": r["started_at"],
            "ended_at": r["ended_at"],
            "prompt_count": r["prompt_count"],
            "tool_use_count": r["tool_use_count"],
            "models_used": json.loads(r["models_used"]),
            "git_branch": r["git_branch"],
            "topics": json.loads(r["topics"]),
            "summary": r["summary"],
        }
