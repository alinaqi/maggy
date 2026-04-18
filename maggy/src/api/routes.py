"""REST API routes — wraps services. All routes under /api/*."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["maggy"])


def _auth(request: Request, x_api_key: str | None) -> None:
    """Simple token check. Bypassed when auth_mode='local'."""
    cfg = request.app.state.cfg
    if cfg.dashboard.auth_mode == "local":
        return
    expected = cfg.dashboard.api_key
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


# ── Health + Config ──────────────────────────────────────────────────────

@router.get("/health")
async def health(request: Request) -> dict:
    cfg = request.app.state.cfg
    return {
        "status": "ok",
        "version": "0.1.0",
        "provider": cfg.issue_tracker.provider,
        "org": cfg.org.name,
        "codebases": len(cfg.codebases),
        "competitors_enabled": bool(cfg.competitors.categories),
    }


@router.get("/config")
async def get_config(request: Request, x_api_key: str | None = Header(None)) -> dict:
    _auth(request, x_api_key)
    cfg = request.app.state.cfg
    # Redact secrets before returning
    return {
        "org": {"name": cfg.org.name, "domain": cfg.org.domain},
        "issue_tracker": {"provider": cfg.issue_tracker.provider},
        "codebases": [{"key": c.key, "path": c.path} for c in cfg.codebases],
        "competitors": {"categories": cfg.competitors.categories, "seed": cfg.competitors.seed},
        "okrs": {"source": cfg.okrs.source, "count": len(cfg.okrs.items)},
        "ai": {"provider": cfg.ai.provider, "model": cfg.ai.model, "has_key": bool(cfg.ai.api_key)},
    }


# ── Inbox ────────────────────────────────────────────────────────────────

@router.get("/inbox")
async def get_inbox(request: Request, refresh: bool = Query(False), x_api_key: str | None = Header(None)) -> dict:
    _auth(request, x_api_key)
    items = await request.app.state.inbox.get_prioritized(force_refresh=refresh)
    return {"items": items, "total": len(items)}


@router.get("/followed")
async def get_followed(request: Request, x_api_key: str | None = Header(None)) -> dict:
    _auth(request, x_api_key)
    tasks = await request.app.state.provider.list_followed(limit=50)
    return {
        "items": [
            {
                "id": t.id, "title": t.title, "board": t.board, "url": t.url,
                "assignee": t.assignee, "updated_at": t.updated_at, "labels": t.labels,
            }
            for t in tasks
        ],
        "total": len(tasks),
    }


# ── Task detail + comments ───────────────────────────────────────────────

@router.get("/task/{task_id:path}")
async def get_task(request: Request, task_id: str, x_api_key: str | None = Header(None)) -> dict:
    _auth(request, x_api_key)
    task = await request.app.state.provider.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    comments = await request.app.state.provider.get_comments(task_id)
    return {
        "task": {
            "id": task.id, "title": task.title, "description": task.description,
            "status": task.status, "assignee": task.assignee, "url": task.url,
            "labels": task.labels, "board": task.board,
            "created_at": task.created_at, "updated_at": task.updated_at,
        },
        "comments": [{"id": c.id, "author": c.author, "text": c.text, "created_at": c.created_at}
                     for c in comments],
    }


class CommentRequest(BaseModel):
    text: str


@router.post("/task/{task_id:path}/comment")
async def post_comment(request: Request, task_id: str, body: CommentRequest, x_api_key: str | None = Header(None)) -> dict:
    _auth(request, x_api_key)
    comment = await request.app.state.provider.add_comment(task_id, body.text)
    if not comment:
        raise HTTPException(status_code=500, detail="Failed to post comment")
    return {"ok": True, "comment": {"id": comment.id, "text": comment.text, "created_at": comment.created_at}}


class StatusRequest(BaseModel):
    status: str


@router.post("/task/{task_id:path}/status")
async def update_status(request: Request, task_id: str, body: StatusRequest, x_api_key: str | None = Header(None)) -> dict:
    _auth(request, x_api_key)
    ok = await request.app.state.provider.update_status(task_id, body.status)
    return {"ok": ok}


# ── Execute ──────────────────────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    task_id: str
    mode: str = "tdd"               # "tdd" | "plan"
    working_dir: str | None = None  # override; otherwise auto-picked


@router.post("/execute")
async def execute(request: Request, body: ExecuteRequest, x_api_key: str | None = Header(None)) -> dict:
    _auth(request, x_api_key)
    try:
        session_id = await request.app.state.executor.start(
            task_id=body.task_id, mode=body.mode, working_dir=body.working_dir,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"session_id": session_id, "status": "running"}


@router.get("/execute/sessions")
async def list_sessions(request: Request, x_api_key: str | None = Header(None)) -> list[dict]:
    _auth(request, x_api_key)
    return request.app.state.executor.list_sessions()


@router.get("/execute/sessions/{session_id}")
async def get_session(request: Request, session_id: str, x_api_key: str | None = Header(None)) -> dict:
    _auth(request, x_api_key)
    s = request.app.state.executor.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s


# ── Competitors ──────────────────────────────────────────────────────────

@router.get("/competitors")
async def list_competitors(request: Request, x_api_key: str | None = Header(None)) -> list[dict]:
    _auth(request, x_api_key)
    return request.app.state.competitors.list_all()


@router.post("/competitors/discover")
async def discover_competitors(request: Request, x_api_key: str | None = Header(None)) -> dict:
    _auth(request, x_api_key)
    return await request.app.state.competitors.discover()


@router.post("/competitors/monitor")
async def trigger_monitoring(request: Request, x_api_key: str | None = Header(None)) -> dict:
    _auth(request, x_api_key)
    return await request.app.state.competitors.monitor_all()


@router.get("/competitors/news")
async def get_competitor_news(request: Request, limit: int = Query(100), x_api_key: str | None = Header(None)) -> list[dict]:
    _auth(request, x_api_key)
    return request.app.state.competitors.get_news(limit=limit)


@router.get("/competitors/news/summary")
async def get_briefing(request: Request, refresh: bool = Query(False), x_api_key: str | None = Header(None)) -> dict:
    _auth(request, x_api_key)
    return await request.app.state.competitors.get_daily_briefing(refresh=refresh)
