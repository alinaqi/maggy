"""Refresh endpoint — pull and summarize recent CLI sessions."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, Header, Query, Request
from pydantic import BaseModel

from .auth import check_auth

router = APIRouter(prefix="/api", tags=["refresh"])


@router.get("/refresh")
async def refresh_sessions(
    request: Request,
    limit: int = Query(3, ge=1, le=10),
    project: str | None = Query(None),
    x_api_key: str | None = Header(None),
) -> dict:
    check_auth(request, x_api_key)
    svc = getattr(request.app.state, "refresh", None)
    if not svc:
        return {"sessions": []}
    digests = svc.refresh(limit=limit, project_path=project)
    return {"sessions": [asdict(d) for d in digests]}


class ImportRequest(BaseModel):
    session_id: str
    target_session_id: str


@router.post("/refresh/import")
async def import_session(
    request: Request,
    body: ImportRequest,
    x_api_key: str | None = Header(None),
) -> dict:
    check_auth(request, x_api_key)
    svc = getattr(request.app.state, "refresh", None)
    store = getattr(request.app.state, "session_store", None)
    if not svc or not store:
        return {"imported": 0}
    digests = svc.refresh(limit=20)
    match = next(
        (d for d in digests if d.session_id == body.session_id),
        None,
    )
    if not match:
        return {"imported": 0}
    chat = getattr(request.app.state, "chat", None)
    session = chat.get_session(body.target_session_id) if chat else None
    count = 0
    ctx_lines = [f"[Imported from {match.cli.upper()} CLI session {match.session_id[:8]}]"]
    for turn in match.turns:
        role = "assistant" if turn["role"] == "assistant" else "user"
        store.append_message(body.target_session_id, role, turn["text"])
        if session:
            from maggy.services.chat_models import ChatMessage
            session.messages.append(ChatMessage(role=role, content=turn["text"]))
        label = "User" if role == "user" else "Assistant"
        ctx_lines.append(f"{label}: {turn['text']}")
        count += 1
    if session:
        session.history_context = "\n".join(ctx_lines)
    return {"imported": count, "project": match.project}


@router.get("/quick-actions")
async def quick_actions(
    request: Request,
    project_path: str | None = Query(None),
    x_api_key: str | None = Header(None),
) -> dict:
    check_auth(request, x_api_key)
    actions: list[dict] = []
    svc = getattr(request.app.state, "refresh", None)
    if svc and project_path:
        sessions = svc.refresh(limit=1, project_path=project_path)
        if sessions:
            ago = sessions[0].last_prompt[:60]
            actions.append({
                "cmd": "/refresh",
                "label": "Continue CLI",
                "icon": "fa-rotate",
                "hint": f"Import: {ago}",
            })
    if project_path:
        p = Path(project_path)
        has_git = (p / ".git").exists()
        if has_git:
            actions.append({
                "cmd": "!git log --oneline -3",
                "label": "Recent commits",
                "icon": "fa-code-commit",
                "hint": "See latest changes",
            })
        has_tests = any(p.glob("tests/test_*.py")) or any(p.glob("test/**"))
        if has_tests:
            actions.append({
                "cmd": "!python3 -m pytest tests/ -x -q 2>&1 | tail -5",
                "label": "Run tests",
                "icon": "fa-flask-vial",
                "hint": "Quick test check",
            })
    actions.append({
        "cmd": "/status",
        "label": "Analyze",
        "icon": "fa-microscope",
        "hint": "Project health",
    })
    actions.append({
        "cmd": "/mnemos",
        "label": "Memory",
        "icon": "fa-brain",
        "hint": "Build memory graph",
    })
    return {"actions": actions[:5]}
