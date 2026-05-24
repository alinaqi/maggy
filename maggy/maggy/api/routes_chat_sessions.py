"""Chat session CRUD + auto-connect endpoints."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from maggy.api.auth import check_auth
from maggy.api.routes_chat import _require_chat

router = APIRouter(prefix="/api/chat", tags=["chat"])

logger = logging.getLogger(__name__)


async def _emit_project_connected(
    pm, project_key: str, working_dir: str, session_id: str,
) -> None:
    """Emit project.connected event for plugin hooks."""
    if not pm:
        return
    try:
        await pm.emit("project.connected", {
            "project_key": project_key,
            "working_dir": working_dir,
            "session_id": session_id,
        })
    except Exception:
        logger.debug("project.connected emit failed", exc_info=True)


class CreateSessionRequest(BaseModel):
    project_key: str
    project_path: str | None = None
    history_context: str | None = None


@router.post("/auto-connect")
async def auto_connect(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Auto-connect to all active projects."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    activity = getattr(request.app.state, "activity", None)
    if not activity:
        return {"sessions": []}
    data = activity.get_activity()
    sessions = chat.auto_connect(data.get("sessions", []))
    history = getattr(request.app.state, "history", None)
    recent = data.get("recent", [])
    pm = getattr(request.app.state, "plugins", None)
    for s in sessions:
        asyncio.create_task(
            _emit_project_connected(pm, s.project_key, s.working_dir, s.id),
        )
    return {"sessions": [_enrich_and_format(s, history, recent) for s in sessions]}


def _enrich_and_format(s, history, recent: list[dict]) -> dict:
    """Build context and format response. Never auto-resolve stale session IDs."""
    from maggy.services.chat_context import build_project_context
    ctx = build_project_context(history, s.working_dir, s.project_key, recent)
    s.history_context = ctx
    return {
        "id": s.id, "project_key": s.project_key, "working_dir": s.working_dir,
        "repo_dir": getattr(s, "repo_dir", ""),
        "label": getattr(s, "label", ""),
        "status": s.status, "messages": len(s.messages),
        "history_context": ctx, "has_resume_id": bool(s.claude_session_id),
    }


@router.post("/preload")
async def preload_sessions(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Create one session per configured codebase."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    cfg = getattr(request.app.state, "cfg", None)
    if not cfg or not cfg.codebases:
        return {"created": 0, "sessions": []}
    created = []
    for cb in cfg.codebases:
        existing = chat.find_by_project(cb.key)
        if existing:
            continue
        try:
            s = chat.create_session(cb.key, cb.path)
            created.append(s)
        except (ValueError, OSError):
            continue
    _resolve_all_sessions(chat)
    pm = getattr(request.app.state, "plugins", None)
    for s in created:
        asyncio.create_task(
            _emit_project_connected(pm, s.project_key, s.working_dir, s.id),
        )
    all_sessions = [
        _format_session(s) for s in chat.list_sessions()
    ]
    return {"created": len(created), "sessions": all_sessions}


def _resolve_all_sessions(chat) -> None:
    """Load Claude history for display (not for --resume)."""
    from maggy.services.chat_context import resolve_claude_session_id
    for s in chat.list_sessions():
        if s.messages:
            continue
        sid = resolve_claude_session_id(s.working_dir)
        if sid:
            _load_history(s, getattr(chat, "_store", None), sid)


def _load_history(s, store, history_sid: str) -> None:
    """Load Claude conversation history for display only.

    Does NOT set claude_session_id — history is read-only
    context, not a session to --resume into.
    """
    from maggy.services.chat_history import load_claude_history
    from maggy.services.chat_models import ChatMessage
    msgs = load_claude_history(s.working_dir, history_sid)
    for m in msgs:
        cm = ChatMessage(
            role=m["role"], content=m["content"],
            timestamp=m.get("timestamp", ""),
        )
        s.messages.append(cm)
        if store:
            store.append_message(s.id, cm.role, cm.content)


def _format_session(s) -> dict:
    """Format a session for API response."""
    return {
        "id": s.id, "project_key": s.project_key,
        "working_dir": s.working_dir, "repo_dir": s.repo_dir,
        "label": s.label, "status": s.status,
        "messages": len(s.messages),
        "has_resume_id": bool(s.messages),
    }


@router.post("/sessions")
async def create_session(
    request: Request,
    body: CreateSessionRequest,
    x_api_key: str | None = Header(None),
) -> dict:
    """Create a new chat session."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    try:
        session = chat.create_session(body.project_key, project_path=body.project_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if body.history_context:
        session.history_context = body.history_context
    pm = getattr(request.app.state, "plugins", None)
    asyncio.create_task(
        _emit_project_connected(pm, session.project_key, session.working_dir, session.id),
    )
    return {"id": session.id, "project_key": session.project_key, "working_dir": session.working_dir, "repo_dir": session.repo_dir, "isolation": session.isolation, "label": session.label, "status": session.status}


@router.get("/sessions")
async def list_sessions(
    request: Request,
    x_api_key: str | None = Header(None),
) -> list[dict]:
    """List all chat sessions."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    return [
        {"id": s.id, "project_key": s.project_key, "working_dir": s.working_dir, "repo_dir": s.repo_dir, "isolation": s.isolation, "label": s.label, "status": s.status, "created_at": s.created_at, "messages": len(s.messages)}
        for s in chat.list_sessions()
    ]


@router.get("/sessions/{session_id}")
async def get_session(
    request: Request, session_id: str,
    x_api_key: str | None = Header(None),
) -> dict:
    """Get session details + message history."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    s = chat.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": s.id, "project_key": s.project_key, "working_dir": s.working_dir,
        "status": s.status, "created_at": s.created_at,
        "history_context": s.history_context, "messages": [asdict(m) for m in s.messages],
    }


class RenameSessionRequest(BaseModel):
    label: str


@router.patch("/sessions/{session_id}")
async def rename_session(
    request: Request, session_id: str,
    body: RenameSessionRequest,
    x_api_key: str | None = Header(None),
) -> dict:
    """Rename a chat session."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    if not chat.rename_session(session_id, body.label.strip()):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True, "label": body.label.strip()}


@router.delete("/sessions/{session_id}")
async def delete_session(
    request: Request, session_id: str,
    x_api_key: str | None = Header(None),
) -> dict:
    """Delete a chat session."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    if not chat.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}
