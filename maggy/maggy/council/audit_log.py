"""Council audit log — SQLite persistence for deliberation decisions."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from maggy.council.models import (
    BlastAnalysis,
    DeliberationResult,
    ExecutionDecision,
)

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS council_audit (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    session_id  TEXT    NOT NULL,
    rounds      INTEGER NOT NULL,
    approve_cnt INTEGER NOT NULL,
    threshold   INTEGER NOT NULL,
    approved    INTEGER NOT NULL,
    blast_score TEXT    NOT NULL,
    severity    TEXT    NOT NULL,
    action      TEXT    NOT NULL,
    reason      TEXT    NOT NULL DEFAULT '',
    votes_json  TEXT    NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_ca_session ON council_audit(session_id);
CREATE INDEX IF NOT EXISTS idx_ca_ts ON council_audit(timestamp);
"""


class AuditLog:
    def __init__(self, db_path: Path):
        self._path = db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._path))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")  # parallel reviewers write (T4)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def record(
        self,
        session_id: str,
        delib: DeliberationResult,
        blast: BlastAnalysis,
        decision: ExecutionDecision,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        votes = json.dumps([v.to_dict() for v in delib.final_votes])
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO council_audit "
                "(timestamp,session_id,rounds,approve_cnt,threshold,"
                "approved,blast_score,severity,action,reason,votes_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    now, session_id, delib.rounds_needed,
                    delib.approve_count, delib.threshold,
                    int(delib.approved),
                    f"{blast.files_changed}f/{blast.functions_affected}fn",
                    blast.severity, decision.action,
                    decision.reason, votes,
                ),
            )

    def recent(self, limit: int = 20, session_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM council_audit"
        params: list = []
        if session_id:
            sql += " WHERE session_id = ?"
            params.append(session_id)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN action='AUTO_EXECUTE' THEN 1 ELSE 0 END) as auto_executed, "
                "SUM(CASE WHEN action='HUMAN_REVIEW' THEN 1 ELSE 0 END) as human_reviewed "
                "FROM council_audit"
            ).fetchone()
        return {
            "total": row[0] or 0,
            "auto_executed": row[1] or 0,
            "human_reviewed": row[2] or 0,
        }
