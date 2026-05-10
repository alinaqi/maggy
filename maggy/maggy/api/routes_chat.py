"""Chat API routes — interactive Claude sessions via SSE."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from maggy.api.auth import check_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _require_chat(request: Request):
    chat = getattr(request.app.state, "chat", None)
    if chat is None:
        raise HTTPException(
            status_code=503,
            detail="Chat service not available.",
        )
    return chat


class CreateSessionRequest(BaseModel):
    project_key: str
    project_path: str | None = None


class SendMessageRequest(BaseModel):
    message: str


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
    active = data.get("sessions", [])
    recent = data.get("recent", [])
    sessions = chat.auto_connect(active)
    history = getattr(request.app.state, "history", None)
    result = []
    for s in sessions:
        ctx = _enrich_session(s, history, recent)
        result.append(_session_summary(s, ctx))
    return {"sessions": result}


def _enrich_session(s, history, recent: list[dict]) -> str:
    """Build context and resolve session ID."""
    from maggy.services.chat_context import (
        build_project_context,
        resolve_claude_session_id,
    )
    ctx = build_project_context(
        history, s.working_dir, s.project_key, recent,
    )
    s.history_context = ctx
    if not s.claude_session_id:
        sid = resolve_claude_session_id(s.working_dir)
        if sid:
            s.claude_session_id = sid
    return ctx


def _session_summary(s, context: str) -> dict:
    """Format session for API response."""
    return {
        "id": s.id,
        "project_key": s.project_key,
        "working_dir": s.working_dir,
        "status": s.status,
        "messages": len(s.messages),
        "history_context": context,
        "has_resume_id": bool(s.claude_session_id),
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
        session = chat.create_session(
            body.project_key, project_path=body.project_path,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "id": session.id,
        "project_key": session.project_key,
        "working_dir": session.working_dir,
        "status": session.status,
    }


@router.get("/sessions")
async def list_sessions(
    request: Request,
    x_api_key: str | None = Header(None),
) -> list[dict]:
    """List all chat sessions."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    return [
        {
            "id": s.id,
            "project_key": s.project_key,
            "status": s.status,
            "created_at": s.created_at,
            "messages": len(s.messages),
        }
        for s in chat.list_sessions()
    ]


@router.get("/sessions/{session_id}")
async def get_session(
    request: Request,
    session_id: str,
    x_api_key: str | None = Header(None),
) -> dict:
    """Get session details + message history."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    s = chat.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "id": s.id,
        "project_key": s.project_key,
        "working_dir": s.working_dir,
        "status": s.status,
        "created_at": s.created_at,
        "history_context": s.history_context,
        "messages": [asdict(m) for m in s.messages],
    }


@router.post("/sessions/{session_id}/send")
async def send_message(
    request: Request,
    session_id: str,
    body: SendMessageRequest,
    x_api_key: str | None = Header(None),
):
    """Send a message and stream response via SSE."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    s = chat.get_session(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message required")

    async def event_stream():
        async for chunk in chat.send(session_id, body.message):
            data = json.dumps(chunk)
            yield f"data: {data}\n\n"
        yield "data: {\"type\": \"done\"}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    request: Request,
    session_id: str,
    x_api_key: str | None = Header(None),
) -> dict:
    """Delete a chat session."""
    check_auth(request, x_api_key)
    chat = _require_chat(request)
    ok = chat.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}
