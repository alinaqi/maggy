"""Approval gate — inbox-based review channel for write operations."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class ApprovalRequest:
    action: str
    risk: str
    context: str
    tool_calls: list[dict] = field(default_factory=list)
    status: str = "pending"
    id: str = ""
    created_at: str = ""
    resolved_at: str | None = None
    resolved_by: str | None = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()


class ApprovalStore:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(
            db_path, check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                action TEXT NOT NULL,
                risk TEXT NOT NULL,
                context TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                resolved_by TEXT
            )
        """)
        self._conn.commit()

    def save(self, req: ApprovalRequest) -> None:
        self._conn.execute(
            "INSERT INTO approvals (id, action, risk, context, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (req.id, req.action, req.risk, req.context,
             req.status, req.created_at),
        )
        self._conn.commit()

    def get(self, request_id: str) -> ApprovalRequest | None:
        row = self._conn.execute(
            "SELECT id, action, risk, context, status, "
            "created_at, resolved_at, resolved_by "
            "FROM approvals WHERE id = ?",
            (request_id,),
        ).fetchone()
        if not row:
            return None
        return ApprovalRequest(
            id=row[0], action=row[1], risk=row[2],
            context=row[3], status=row[4],
            created_at=row[5], resolved_at=row[6],
            resolved_by=row[7],
        )

    def resolve(
        self, request_id: str, decision: str, by: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE approvals SET status=?, resolved_at=?, resolved_by=? "
            "WHERE id=?",
            (decision, now, by, request_id),
        )
        self._conn.commit()

    def pending(self) -> list[ApprovalRequest]:
        rows = self._conn.execute(
            "SELECT id, action, risk, context, status, "
            "created_at, resolved_at, resolved_by "
            "FROM approvals WHERE status='pending' "
            "ORDER BY created_at DESC",
        ).fetchall()
        return [self._row_to_req(r) for r in rows]

    def history(self, limit: int = 50) -> list[ApprovalRequest]:
        rows = self._conn.execute(
            "SELECT id, action, risk, context, status, "
            "created_at, resolved_at, resolved_by "
            "FROM approvals WHERE status != 'pending' "
            "ORDER BY resolved_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_req(r) for r in rows]

    def _row_to_req(self, row: tuple) -> ApprovalRequest:
        return ApprovalRequest(
            id=row[0], action=row[1], risk=row[2],
            context=row[3], status=row[4],
            created_at=row[5], resolved_at=row[6],
            resolved_by=row[7],
        )


class ApprovalGate:
    def __init__(self, store: ApprovalStore | None) -> None:
        self._store = store

    def classify_risk(self, risk: str) -> str:
        if risk == "read":
            return "auto"
        return "review"
