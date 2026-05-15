"""iCPG inspection API — browse reason graphs across projects."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Header, Query, Request

from .auth import check_auth

router = APIRouter(prefix="/api/icpg", tags=["icpg"])


def _find_stores(cfg) -> list[dict]:
    """Find all .icpg/reason.db across configured codebases."""
    stores = []
    for cb in cfg.codebases:
        db = Path(cb.path) / ".icpg" / "reason.db"
        if db.exists():
            stores.append({"key": cb.key, "path": str(db)})
    return stores


def _resolve_db(cfg, project_key: str) -> str | None:
    """Find reason.db path for a project key."""
    for cb in cfg.codebases:
        if cb.key == project_key:
            db = Path(cb.path) / ".icpg" / "reason.db"
            return str(db) if db.exists() else None
    return None


def _query(db_path: str, sql: str, params: tuple = ()) -> list[dict]:
    """Run a read-only query against a reason.db."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _stats(db_path: str) -> dict:
    """Get counts from a reason.db."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        r = conn.execute("SELECT COUNT(*) FROM reasons").fetchone()[0]
        s = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        e = conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        d = conn.execute(
            "SELECT COUNT(*) FROM drift_events WHERE resolved=0"
        ).fetchone()[0]
        return {"reasons": r, "symbols": s, "edges": e, "drift": d}
    finally:
        conn.close()


@router.get("/overview")
async def overview(
    request: Request, x_api_key: str | None = Header(None),
) -> dict:
    """Aggregate iCPG stats across all codebases."""
    check_auth(request, x_api_key)
    cfg = request.app.state.cfg
    projects = []
    for store in _find_stores(cfg):
        projects.append({"key": store["key"], **_stats(store["path"])})
    total = {
        k: sum(p[k] for p in projects)
        for k in ("reasons", "symbols", "edges", "drift")
    }
    return {"projects": projects, "total": total}


@router.get("/{project_key}/reasons")
async def list_reasons(
    request: Request, project_key: str,
    status: str | None = Query(None),
    limit: int = Query(50, le=200),
    x_api_key: str | None = Header(None),
) -> dict:
    """List ReasonNodes for a project."""
    check_auth(request, x_api_key)
    db = _resolve_db(request.app.state.cfg, project_key)
    if not db:
        return {"error": "No iCPG database for this project"}
    sql = "SELECT id, goal, decision_type, status, owner, source, scope, created_at FROM reasons"
    params: tuple = ()
    if status:
        sql += " WHERE status = ?"
        params = (status,)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params = (*params, limit)
    rows = _query(db, sql, params)
    for r in rows:
        r["scope"] = json.loads(r.get("scope", "[]"))
    return {"project": project_key, "reasons": rows}


@router.get("/{project_key}/drift")
async def list_drift(
    request: Request, project_key: str,
    x_api_key: str | None = Header(None),
) -> dict:
    """List unresolved drift events for a project."""
    check_auth(request, x_api_key)
    db = _resolve_db(request.app.state.cfg, project_key)
    if not db:
        return {"error": "No iCPG database for this project"}
    rows = _query(
        db,
        """SELECT d.id, d.severity, d.description, d.detected_at,
                  d.drift_dimensions, s.name as symbol_name, s.file_path
           FROM drift_events d
           LEFT JOIN symbols s ON d.symbol_id = s.id
           WHERE d.resolved = 0
           ORDER BY d.severity DESC LIMIT 50""",
    )
    for r in rows:
        r["drift_dimensions"] = json.loads(
            r.get("drift_dimensions", "[]")
        )
    return {"project": project_key, "drift": rows}


@router.get("/{project_key}/graph")
async def graph_data(
    request: Request, project_key: str,
    limit: int = Query(100, le=500),
    x_api_key: str | None = Header(None),
) -> dict:
    """Return nodes + edges for graph visualization."""
    check_auth(request, x_api_key)
    db = _resolve_db(request.app.state.cfg, project_key)
    if not db:
        return {"error": "No iCPG database for this project"}
    reasons = _query(
        db,
        "SELECT id, goal, decision_type, status FROM reasons "
        "ORDER BY created_at DESC LIMIT ?",
        (limit,),
    )
    if not reasons:
        return {"nodes": [], "edges": []}
    ph = ",".join("?" * len(reasons))
    rids = tuple(r["id"] for r in reasons)
    edges = _query(
        db,
        f"SELECT from_id, to_id, edge_type FROM edges "
        f"WHERE from_id IN ({ph}) LIMIT ?",
        (*rids, limit * 3),
    )
    sids = list({e["to_id"] for e in edges})
    symbols = []
    if sids:
        sp = ",".join("?" * len(sids))
        symbols = _query(
            db,
            f"SELECT id, name, symbol_type, file_path FROM symbols "
            f"WHERE id IN ({sp})",
            tuple(sids),
        )
    nodes = [
        {"id": r["id"], "label": r["goal"][:60], "type": "reason",
         "status": r["status"]}
        for r in reasons
    ] + [
        {"id": s["id"], "label": s["name"], "type": "symbol",
         "symbol_type": s["symbol_type"]}
        for s in symbols
    ]
    links = [
        {"from": e["from_id"], "to": e["to_id"], "type": e["edge_type"]}
        for e in edges
    ]
    return {"nodes": nodes, "edges": links}
