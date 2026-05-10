"""SQLite event store — append-only with archive support."""

from __future__ import annotations

import gzip
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .header import EventHeader

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    event_type TEXT NOT NULL,
    task_id TEXT NOT NULL DEFAULT '',
    project_id TEXT NOT NULL DEFAULT '',
    agent_id TEXT NOT NULL DEFAULT '',
    model_id TEXT NOT NULL DEFAULT '',
    parent_event_id TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_task
    ON events(task_id);
CREATE INDEX IF NOT EXISTS idx_events_type
    ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_project
    ON events(project_id);
CREATE INDEX IF NOT EXISTS idx_events_ts
    ON events(timestamp);
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


class EventStore:
    """Append-only SQLite event store."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with _connect(self._db_path) as conn:
            conn.executescript(SCHEMA)

    def write(
        self, header: EventHeader, payload: dict,
    ) -> None:
        """Append an event."""
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO events "
                "(event_id, event_type, task_id, "
                "project_id, agent_id, model_id, "
                "parent_event_id, timestamp, payload) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    header.event_id, header.event_type,
                    header.task_id, header.project_id,
                    header.agent_id, header.model_id,
                    header.parent_event_id,
                    header.timestamp,
                    json.dumps(payload),
                ),
            )
            conn.commit()

    def query(
        self,
        task_id: str | None = None,
        event_type: str | None = None,
        project_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query events with filters."""
        clauses: list[str] = []
        params: list = []
        if task_id:
            clauses.append("task_id = ?")
            params.append(task_id)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)

        where = (
            f"WHERE {' AND '.join(clauses)}"
            if clauses else ""
        )
        sql = (
            f"SELECT payload FROM events {where} "
            f"ORDER BY timestamp ASC LIMIT ?"
        )
        params.append(limit)

        with _connect(self._db_path) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def count(
        self,
        event_type: str | None = None,
        project_id: str | None = None,
    ) -> int:
        """Count events matching filters."""
        clauses: list[str] = []
        params: list[str] = []
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)

        where = (
            f"WHERE {' AND '.join(clauses)}"
            if clauses else ""
        )
        with _connect(self._db_path) as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM events {where}",
                params,
            ).fetchone()
        return int(row[0])

    def archive_old(
        self,
        days: int = 90,
        archive_dir: Path | None = None,
    ) -> int:
        """Archive events older than N days."""
        from datetime import datetime, timedelta, timezone
        cutoff = (
            datetime.now(timezone.utc)
            - timedelta(days=days)
        ).isoformat()

        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT payload FROM events "
                "WHERE timestamp < ?",
                (cutoff,),
            ).fetchall()

            if not rows:
                return 0

            out_dir = archive_dir or (
                self._db_path.parent / "events_archive"
            )
            out_dir.mkdir(parents=True, exist_ok=True)
            archive_file = (
                out_dir / f"events_{cutoff[:10]}.jsonl.gz"
            )

            with gzip.open(archive_file, "wt") as f:
                for r in rows:
                    f.write(r["payload"] + "\n")

            conn.execute(
                "DELETE FROM events WHERE timestamp < ?",
                (cutoff,),
            )
            conn.commit()

        return len(rows)
