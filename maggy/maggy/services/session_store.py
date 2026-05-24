"""Session store — persists chat sessions + messages to SQLite."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project_key TEXT NOT NULL,
    working_dir TEXT NOT NULL,
    claude_session_id TEXT NOT NULL DEFAULT '',
    repo_dir TEXT NOT NULL DEFAULT '',
    isolation TEXT NOT NULL DEFAULT 'none',
    label TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_msg_session
    ON messages(session_id);
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


class SessionStore:
    """SQLite-backed session persistence."""

    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        with _connect(self._db_path) as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Add columns missing from older schemas."""
        cols = {
            r[1] for r in conn.execute("PRAGMA table_info(sessions)")
        }
        for col, default in [
            ("repo_dir", "''"),
            ("isolation", "'none'"),
            ("label", "''"),
            ("session_cleared", "0"),
        ]:
            if col not in cols:
                conn.execute(
                    f"ALTER TABLE sessions ADD COLUMN {col} "
                    f"TEXT NOT NULL DEFAULT {default}",
                )
        conn.commit()

    def save_session(
        self, sid: str, project_key: str,
        working_dir: str, claude_session_id: str,
        repo_dir: str = "", isolation: str = "none",
        label: str = "",
    ) -> None:
        """Insert or update a session."""
        now = datetime.now(timezone.utc).isoformat()
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO sessions "
                "(id, project_key, working_dir, "
                "claude_session_id, repo_dir, isolation, "
                "label, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "claude_session_id = excluded.claude_session_id",
                (sid, project_key, working_dir,
                 claude_session_id, repo_dir, isolation,
                 label, now),
            )
            conn.commit()

    def update_claude_id(self, sid: str, claude_id: str) -> None:
        """Update Claude CLI session ID."""
        with _connect(self._db_path) as conn:
            conn.execute(
                "UPDATE sessions SET claude_session_id = ? "
                "WHERE id = ?",
                (claude_id, sid),
            )
            conn.commit()

    def mark_session_cleared(self, sid: str) -> None:
        """Mark session as cleared — prevents stale ID re-resolution."""
        with _connect(self._db_path) as conn:
            conn.execute(
                "UPDATE sessions SET session_cleared = '1', "
                "claude_session_id = '' WHERE id = ?",
                (sid,),
            )
            conn.commit()

    def update_label(self, sid: str, label: str) -> None:
        """Update session label."""
        with _connect(self._db_path) as conn:
            conn.execute(
                "UPDATE sessions SET label = ? WHERE id = ?",
                (label, sid),
            )
            conn.commit()

    def load_sessions(self) -> list[dict]:
        """Load all sessions."""
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM sessions "
                "ORDER BY created_at DESC",
            ).fetchall()
        return [dict(r) for r in rows]

    def append_message(
        self, sid: str, role: str, content: str,
    ) -> None:
        """Append a message to a session."""
        now = datetime.now(timezone.utc).isoformat()
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO messages "
                "(session_id, role, content, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (sid, role, content, now),
            )
            conn.commit()

    def load_messages(self, sid: str) -> list[dict]:
        """Load messages for a session."""
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT role, content, timestamp "
                "FROM messages WHERE session_id = ? "
                "ORDER BY id",
                (sid,),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_session(self, sid: str) -> None:
        """Delete session and its messages."""
        with _connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM messages WHERE session_id = ?",
                (sid,),
            )
            conn.execute(
                "DELETE FROM sessions WHERE id = ?",
                (sid,),
            )
            conn.commit()
