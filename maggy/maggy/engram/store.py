"""SQLite store for Engram records with namespace isolation."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .record import EngramRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS engrams (
    engram_id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'explicit',
    validity TEXT NOT NULL DEFAULT 'active',
    confidence REAL NOT NULL DEFAULT 1.0,
    tags TEXT NOT NULL DEFAULT '[]',
    source_task TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_engram_ns
    ON engrams(namespace);
CREATE INDEX IF NOT EXISTS idx_engram_type
    ON engrams(memory_type);
CREATE INDEX IF NOT EXISTS idx_engram_validity
    ON engrams(validity);
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


class EngramStore:
    """SQLite-backed engram storage."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        with _connect(self._db_path) as conn:
            conn.executescript(SCHEMA)

    def write(self, record: EngramRecord) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO engrams "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    record.engram_id,
                    record.namespace,
                    record.memory_type,
                    record.content,
                    record.origin,
                    record.validity,
                    record.confidence,
                    json.dumps(record.tags),
                    record.source_task,
                    record.created_at,
                    record.expires_at,
                ),
            )
            conn.commit()

    def get(
        self, engram_id: str,
    ) -> EngramRecord | None:
        with _connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM engrams "
                "WHERE engram_id=?",
                (engram_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def query(
        self,
        namespace: str | None = None,
        memory_type: str | None = None,
        active_only: bool = True,
        limit: int = 100,
    ) -> list[EngramRecord]:
        clauses: list[str] = []
        params: list = []
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if memory_type:
            clauses.append("memory_type = ?")
            params.append(memory_type)
        if active_only:
            clauses.append("validity = 'active'")

        where = (
            f"WHERE {' AND '.join(clauses)}"
            if clauses else ""
        )
        with _connect(self._db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM engrams {where} "
                f"ORDER BY created_at DESC LIMIT ?",
                params + [limit],
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def count(
        self, namespace: str | None = None,
    ) -> int:
        with _connect(self._db_path) as conn:
            if namespace:
                row = conn.execute(
                    "SELECT COUNT(*) FROM engrams "
                    "WHERE namespace = ?",
                    (namespace,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM engrams",
                ).fetchone()
        return int(row[0])

    def _row_to_record(
        self, r: sqlite3.Row,
    ) -> EngramRecord:
        return EngramRecord(
            engram_id=r["engram_id"],
            namespace=r["namespace"],
            memory_type=r["memory_type"],
            content=r["content"],
            origin=r["origin"],
            validity=r["validity"],
            confidence=r["confidence"],
            tags=json.loads(r["tags"]),
            source_task=r["source_task"],
            created_at=r["created_at"],
            expires_at=r["expires_at"],
        )
