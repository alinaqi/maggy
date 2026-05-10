"""SQLite backing for mesh peers, memories, and quarantine."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS peers (
    peer_id TEXT NOT NULL,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 8080,
    org TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    manual INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (peer_id, org)
);
CREATE TABLE IF NOT EXISTS shared_memories (
    key TEXT NOT NULL,
    org TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source_peer TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    PRIMARY KEY (key, org)
);
CREATE TABLE IF NOT EXISTS quarantine (
    key TEXT NOT NULL,
    org TEXT NOT NULL,
    source_peer TEXT NOT NULL,
    reason TEXT NOT NULL,
    content TEXT NOT NULL,
    quarantined_at TEXT NOT NULL,
    PRIMARY KEY (key, org)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MeshStore:
    """SQLite-backed mesh storage with connection reuse."""

    def __init__(self, db_path: Path) -> None:
        self._db = db_path
        self._lock = threading.Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(db_path), timeout=30.0,
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    # ── Peers ──────────────────────────────────────────

    def upsert_peer(
        self, peer_id: str, name: str,
        address: str, port: int, org: str,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO peers "
                "VALUES (?,?,?,?,?,?,?)",
                (peer_id, name, address, port,
                 org, _now(), 0),
            )
            self._conn.commit()

    def get_peer(
        self, peer_id: str, org: str,
    ) -> dict | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM peers "
                "WHERE peer_id=? AND org=?",
                (peer_id, org),
            ).fetchone()
        return dict(row) if row else None

    def list_peers(
        self, org: str | None = None,
    ) -> list[dict]:
        with self._lock:
            if org:
                rows = self._conn.execute(
                    "SELECT * FROM peers WHERE org=?",
                    (org,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM peers",
                ).fetchall()
        return [dict(r) for r in rows]

    def remove_peer(
        self, peer_id: str, org: str,
    ) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM peers "
                "WHERE peer_id=? AND org=?",
                (peer_id, org),
            )
            self._conn.commit()
        return cur.rowcount > 0

    # ── Memories ───────────────────────────────────────

    def write_memory(
        self, org: str, key: str, memory_type: str,
        content: dict, source_peer: str,
        confidence: float = 1.0,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO shared_memories "
                "VALUES (?,?,?,?,?,?,?)",
                (key, org, memory_type,
                 json.dumps(content),
                 source_peer, confidence, _now()),
            )
            self._conn.commit()

    def list_memories(self, org: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM shared_memories WHERE org=?",
                (org,),
            ).fetchall()
        return [
            {**dict(r), "content": json.loads(r["content"])}
            for r in rows
        ]

    # ── Quarantine ─────────────────────────────────────

    def quarantine_item(
        self, org: str, key: str,
        source: str, reason: str, content: dict,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO quarantine "
                "VALUES (?,?,?,?,?,?)",
                (key, org, source, reason,
                 json.dumps(content), _now()),
            )
            self._conn.commit()

    def promote_item(
        self, org: str, key: str,
    ) -> bool:
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM quarantine "
                "WHERE key=? AND org=?",
                (key, org),
            )
            self._conn.commit()
        return cur.rowcount > 0

    def list_quarantined(self, org: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM quarantine WHERE org=?",
                (org,),
            ).fetchall()
        return [
            {**dict(r), "content": json.loads(r["content"])}
            for r in rows
        ]

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
