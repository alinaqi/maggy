"""SQLite database layer for Mnemos."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from maggy.mnemos.constants import DB_FILENAME
from maggy.mnemos.db_queries import (
    _ts,
    node_to_tuple,
    row_to_checkpoint,
    row_to_node,
)
from maggy.mnemos.models import (
    CheckpointData,
    MnemoNode,
    NodeLink,
)

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS mnemo_nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    task_id TEXT NOT NULL,
    parent_node_id TEXT,
    content TEXT NOT NULL,
    summary TEXT,
    activation_weight REAL DEFAULT 1.0,
    created_at TEXT NOT NULL,
    last_accessed TEXT NOT NULL,
    access_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'ACTIVE',
    origin TEXT DEFAULT 'AGENT_GENERATED',
    confidence REAL DEFAULT 1.0,
    scope_tags TEXT DEFAULT '[]',
    fingerprint TEXT
);

CREATE TABLE IF NOT EXISTS node_links (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    link_type TEXT DEFAULT 'RELATED',
    PRIMARY KEY (source_id, target_id)
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    fatigue REAL NOT NULL,
    summary TEXT NOT NULL,
    graph_json TEXT NOT NULL,
    is_emergency INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS conflict_records (
    id TEXT PRIMARY KEY,
    node_a_id TEXT NOT NULL,
    node_b_id TEXT NOT NULL,
    conflict_type TEXT NOT NULL,
    resolution TEXT NOT NULL,
    resolved_at TEXT NOT NULL
);
"""


class MnemosDB:
    """CRUD operations on the Mnemos SQLite store."""

    def __init__(self, mnemos_dir: Path) -> None:
        self._path = mnemos_dir / DB_FILENAME
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")  # concurrent writers wait (T4)
        self._conn.executescript(_SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "MnemosDB":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def list_tables(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' ORDER BY name"
        ).fetchall()
        return [r["name"] for r in rows]

    # -- nodes --

    def insert_node(self, node: MnemoNode) -> None:
        self._conn.execute(
            "INSERT INTO mnemo_nodes VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            node_to_tuple(node),
        )
        self._conn.commit()

    def get_node(self, node_id: str) -> MnemoNode | None:
        row = self._conn.execute(
            "SELECT * FROM mnemo_nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        return row_to_node(row) if row else None

    def list_nodes(
        self,
        task_id: str | None = None,
        node_type: str | None = None,
    ) -> list[MnemoNode]:
        sql = "SELECT * FROM mnemo_nodes WHERE 1=1"
        params: list[str] = []
        if task_id:
            sql += " AND task_id = ?"
            params.append(task_id)
        if node_type:
            sql += " AND type = ?"
            params.append(node_type)
        rows = self._conn.execute(sql, params).fetchall()
        return [row_to_node(r) for r in rows]

    def count_nodes(self) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) as c FROM mnemo_nodes"
        ).fetchone()
        return row["c"]

    def touch_node(self, node_id: str) -> None:
        now = _ts(datetime.now(timezone.utc))
        self._conn.execute(
            "UPDATE mnemo_nodes SET "
            "access_count = access_count + 1, "
            "last_accessed = ? WHERE id = ?",
            (now, node_id),
        )
        self._conn.commit()

    # -- links --

    def insert_link(self, link: NodeLink) -> None:
        self._conn.execute(
            "INSERT INTO node_links VALUES (?,?,?)",
            (link.source_id, link.target_id, link.link_type),
        )
        self._conn.commit()

    def get_links(self, source_id: str) -> list[NodeLink]:
        rows = self._conn.execute(
            "SELECT * FROM node_links WHERE source_id = ?",
            (source_id,),
        ).fetchall()
        return [
            NodeLink(
                source_id=r["source_id"],
                target_id=r["target_id"],
                link_type=r["link_type"],
            )
            for r in rows
        ]

    # -- checkpoints --

    def insert_checkpoint(self, cp: CheckpointData) -> None:
        self._conn.execute(
            "INSERT INTO checkpoints VALUES (?,?,?,?,?,?,?)",
            (
                cp.id, cp.task_id, _ts(cp.created_at),
                cp.fatigue, cp.summary,
                json.dumps(cp.graph_json),
                1 if cp.is_emergency else 0,
            ),
        )
        self._conn.commit()

    def get_latest_checkpoint(self) -> CheckpointData | None:
        row = self._conn.execute(
            "SELECT * FROM checkpoints "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return row_to_checkpoint(row) if row else None
