"""Chat session CRUD + auto-connect endpoints."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from maggy.api.auth import check_auth
from maggy.api.routes_chat import _require_chat

router = APIRouter(prefix="/api/chat", tags=["chat"])


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
    return {"sessions": [_enrich_and_format(s, history, recent) for s in sessions]}


def _enrich_and_format(s, history, recent: list[dict]) -> dict:
    """Build context, resolve session ID, format response."""
    from maggy.services.chat_context import build_project_context, resolve_claude_session_id
    ctx = build_project_context(history, s.working_dir, s.project_key, recent)
    s.history_context = ctx
    if not s.claude_session_id:
        sid = resolve_claude_session_id(s.working_dir)
        if sid:
            s.claude_session_id = sid
    return {
        "id": s.id, "project_key": s.project_key, "working_dir": s.working_dir,
        "repo_dir": getattr(s, "repo_dir", ""),
        "label": getattr(s, "label", ""),
        "status": s.status, "messages": len(s.messages),
        "history_context": ctx, "has_resume_id": bool(s.claude_session_id),
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
