"""Advanced DB queries and row deserialization for Mnemos."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from maggy.mnemos.models import CheckpointData, MnemoNode


def _ts(dt: datetime) -> str:
    return dt.isoformat()


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def row_to_node(row: sqlite3.Row) -> MnemoNode:
    """Deserialize a DB row into a MnemoNode."""
    return MnemoNode(
        id=row["id"],
        type=row["type"],
        task_id=row["task_id"],
        parent_node_id=row["parent_node_id"],
        content=row["content"],
        summary=row["summary"],
        activation_weight=row["activation_weight"],
        created_at=_parse_ts(row["created_at"]),
        last_accessed=_parse_ts(row["last_accessed"]),
        access_count=row["access_count"],
        status=row["status"],
        origin=row["origin"],
        confidence=row["confidence"],
        scope_tags=json.loads(row["scope_tags"]),
        fingerprint=row["fingerprint"],
    )


def row_to_checkpoint(row: sqlite3.Row) -> CheckpointData:
    """Deserialize a DB row into CheckpointData."""
    return CheckpointData(
        id=row["id"],
        task_id=row["task_id"],
        created_at=_parse_ts(row["created_at"]),
        fatigue=row["fatigue"],
        summary=row["summary"],
        graph_json=json.loads(row["graph_json"]),
        is_emergency=bool(row["is_emergency"]),
    )


def update_node_status(
    conn: sqlite3.Connection, node_id: str, status: str,
) -> None:
    """Set node status."""
    conn.execute(
        "UPDATE mnemo_nodes SET status = ? WHERE id = ?",
        (status, node_id),
    )
    conn.commit()


def update_node_weight(
    conn: sqlite3.Connection, node_id: str, weight: float,
) -> None:
    """Set activation_weight for a node."""
    conn.execute(
        "UPDATE mnemo_nodes SET activation_weight = ? "
        "WHERE id = ?",
        (weight, node_id),
    )
    conn.commit()


def update_node_summary(
    conn: sqlite3.Connection, node_id: str, summary: str,
) -> None:
    """Set summary text (used after compression)."""
    conn.execute(
        "UPDATE mnemo_nodes SET summary = ? WHERE id = ?",
        (summary, node_id),
    )
    conn.commit()


def list_nodes_below_weight(
    conn: sqlite3.Connection, threshold: float,
    node_type: str | None = None,
) -> list[MnemoNode]:
    """Nodes with activation_weight < threshold."""
    sql = (
        "SELECT * FROM mnemo_nodes "
        "WHERE activation_weight < ? AND status = 'ACTIVE'"
    )
    params: list = [threshold]
    if node_type:
        sql += " AND type = ?"
        params.append(node_type)
    rows = conn.execute(sql, params).fetchall()
    return [row_to_node(r) for r in rows]


def bulk_update_status(
    conn: sqlite3.Connection, node_ids: list[str], status: str,
) -> int:
    """Batch status update. Returns count updated."""
    if not node_ids:
        return 0
    placeholders = ",".join("?" for _ in node_ids)
    conn.execute(
        f"UPDATE mnemo_nodes SET status = ? "
        f"WHERE id IN ({placeholders})",
        [status, *node_ids],
    )
    conn.commit()
    return len(node_ids)


def update_node_fingerprint(
    conn: sqlite3.Connection, node_id: str, fp: str,
) -> None:
    """Set fingerprint for a node."""
    conn.execute(
        "UPDATE mnemo_nodes SET fingerprint = ? WHERE id = ?",
        (fp, node_id),
    )
    conn.commit()


def node_to_tuple(node: MnemoNode) -> tuple:
    """Serialize a MnemoNode to a DB-ready tuple."""
    return (
        node.id, node.type, node.task_id,
        node.parent_node_id, node.content,
        node.summary, node.activation_weight,
        _ts(node.created_at), _ts(node.last_accessed),
        node.access_count, node.status, node.origin,
        node.confidence,
        json.dumps(node.scope_tags),
        node.fingerprint,
    )
