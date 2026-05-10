"""KnowledgeGraphService — CRUD for CIKG nodes and edges."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .models import Edge, Node

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    metadata TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_nodes_type
    ON nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_name
    ON nodes(name);

CREATE TABLE IF NOT EXISTS edges (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    metadata TEXT DEFAULT '{}',
    PRIMARY KEY (source_id, target_id, edge_type)
);
CREATE INDEX IF NOT EXISTS idx_edges_source
    ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target
    ON edges(target_id);
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


class KnowledgeGraphService:
    """SQLite-backed knowledge graph."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        with _connect(self._db_path) as conn:
            conn.executescript(SCHEMA)

    def add_node(self, node: Node) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO nodes "
                "VALUES (?,?,?,?,?,?)",
                (
                    node.id, node.node_type, node.name,
                    node.description,
                    json.dumps(node.metadata),
                    node.created_at,
                ),
            )
            conn.commit()

    def get_node(self, node_id: str) -> Node | None:
        with _connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT * FROM nodes WHERE id=?",
                (node_id,),
            ).fetchone()
        if not row:
            return None
        return Node(
            id=row["id"],
            node_type=row["node_type"],
            name=row["name"],
            description=row["description"],
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
        )

    def list_nodes(
        self, node_type: str | None = None,
    ) -> list[Node]:
        with _connect(self._db_path) as conn:
            if node_type:
                rows = conn.execute(
                    "SELECT * FROM nodes "
                    "WHERE node_type=?",
                    (node_type,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM nodes",
                ).fetchall()
        return [
            Node(
                id=r["id"],
                node_type=r["node_type"],
                name=r["name"],
                description=r["description"],
                metadata=json.loads(r["metadata"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def add_edge(self, edge: Edge) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO edges "
                "VALUES (?,?,?,?,?)",
                (
                    edge.source_id, edge.target_id,
                    edge.edge_type, edge.weight,
                    json.dumps(edge.metadata),
                ),
            )
            conn.commit()

    def get_edges(
        self, node_id: str, direction: str = "out",
    ) -> list[Edge]:
        """Get edges. direction: out|in|both."""
        with _connect(self._db_path) as conn:
            edges: list[Edge] = []
            if direction in ("out", "both"):
                for r in conn.execute(
                    "SELECT * FROM edges "
                    "WHERE source_id=?",
                    (node_id,),
                ).fetchall():
                    edges.append(self._row_to_edge(r))
            if direction in ("in", "both"):
                for r in conn.execute(
                    "SELECT * FROM edges "
                    "WHERE target_id=?",
                    (node_id,),
                ).fetchall():
                    edges.append(self._row_to_edge(r))
        return edges

    def neighbors(self, node_id: str) -> list[Node]:
        """Get all nodes connected to this node."""
        edges = self.get_edges(node_id, "both")
        ids = set()
        for e in edges:
            ids.add(e.source_id)
            ids.add(e.target_id)
        ids.discard(node_id)
        return [
            n for n in
            (self.get_node(i) for i in ids)
            if n
        ]

    def delete_node(self, node_id: str) -> None:
        with _connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM nodes WHERE id=?",
                (node_id,),
            )
            conn.execute(
                "DELETE FROM edges "
                "WHERE source_id=? OR target_id=?",
                (node_id, node_id),
            )
            conn.commit()

    def _row_to_edge(
        self, r: sqlite3.Row,
    ) -> Edge:
        return Edge(
            source_id=r["source_id"],
            target_id=r["target_id"],
            edge_type=r["edge_type"],
            weight=r["weight"],
            metadata=json.loads(r["metadata"]),
        )
