"""Pipeline log store — SQLite persistence for pipeline decisions."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from maggy.pipeline.models import PipelineContext, PipelineResult

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS pipeline_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    session_id      TEXT    NOT NULL,
    message_snippet TEXT    NOT NULL,
    model           TEXT    NOT NULL,
    backend         TEXT    NOT NULL,
    blast           INTEGER NOT NULL DEFAULT 0,
    task_type       TEXT    NOT NULL DEFAULT 'general',
    reason          TEXT    NOT NULL DEFAULT '',
    latency_ms      REAL    NOT NULL DEFAULT 0,
    cost_usd        REAL    NOT NULL DEFAULT 0,
    tokens_in       INTEGER NOT NULL DEFAULT 0,
    tokens_out      INTEGER NOT NULL DEFAULT 0,
    success         INTEGER NOT NULL DEFAULT 1,
    error           TEXT    NOT NULL DEFAULT '',
    fallback_used   TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_plog_session ON pipeline_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_plog_ts ON pipeline_logs(timestamp);
"""

_SNIPPET_LEN = 120


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


class PipelineLogStore:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        with _connect(self._db_path) as conn:
            conn.executescript(_SCHEMA)

    def record(self, result: PipelineResult, ctx: PipelineContext) -> None:
        snippet = ctx.message[:_SNIPPET_LEN]
        ts = datetime.now(tz=None).isoformat()
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO pipeline_logs "
                "(timestamp, session_id, message_snippet, model, backend, "
                "blast, task_type, reason, latency_ms, cost_usd, "
                "tokens_in, tokens_out, success, error, fallback_used) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ts, ctx.session_id, snippet, result.model,
                 result.backend, result.blast, result.task_type,
                 result.reason, result.latency_ms, result.cost_usd,
                 result.tokens_in, result.tokens_out,
                 int(result.success), result.error, result.fallback_used),
            )
            conn.commit()

    def recent(
        self, limit: int = 50,
        session_id: str | None = None,
        model: str | None = None,
    ) -> list[dict]:
        clauses, params = [], []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if model:
            clauses.append("model = ?")
            params.append(model)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM pipeline_logs {where} "
                "ORDER BY id DESC LIMIT ?", params,
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self, period: str = "today") -> dict:
        cutoff = _period_cutoff(period)
        with _connect(self._db_path) as conn:
            where, params = "", []
            if cutoff:
                where = "WHERE timestamp >= ?"
                params = [cutoff]
            row = conn.execute(
                f"SELECT COUNT(*) as total, "
                "SUM(cost_usd) as cost, "
                "AVG(latency_ms) as avg_lat, "
                f"SUM(success) as ok FROM pipeline_logs {where}",
                params,
            ).fetchone()
            total = row["total"] or 0
            by_model = conn.execute(
                f"SELECT model, COUNT(*) as calls, "
                "AVG(latency_ms) as avg_latency, "
                "SUM(cost_usd) as cost, "
                f"AVG(success) as success_rate FROM pipeline_logs {where} "
                "GROUP BY model",
                params,
            ).fetchall()
        return {
            "total_calls": total,
            "total_cost": row["cost"] or 0.0,
            "avg_latency_ms": row["avg_lat"] or 0.0,
            "success_rate": (row["ok"] / total) if total else 0.0,
            "by_model": [dict(m) for m in by_model],
        }


def _period_cutoff(period: str) -> str | None:
    if period == "all":
        return None
    now = datetime.now(tz=None)
    if period == "today":
        dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        dt = now - timedelta(days=7)
    elif period == "month":
        dt = now - timedelta(days=30)
    else:
        return None
    return dt.isoformat()
