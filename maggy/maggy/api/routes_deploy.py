"""Deploy REST endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from .auth import check_auth

router = APIRouter(prefix="/api/deploy", tags=["deploy"])


class CreateSessionRequest(BaseModel):
    project: str = Field(..., min_length=1, max_length=200)
    branch: str = Field(default="main", max_length=200)


@router.get("/sessions")
async def list_sessions(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """List all deploy sessions."""
    check_auth(request, x_api_key)
    svc = request.app.state.deploy
    if not svc:
        return {"error": "deploy not configured"}
    return {
        "sessions": [asdict(s) for s in svc.list_sessions()],
    }


@router.get("/sessions/{sid}")
async def get_session(
    request: Request,
    sid: str,
    x_api_key: str | None = Header(None),
) -> dict:
    """Get a specific deploy session."""
    check_auth(request, x_api_key)
    svc = request.app.state.deploy
    if not svc:
        return {"error": "deploy not configured"}
    session = svc.get_session(sid)
    if not session:
        return {"error": "session not found"}
    return asdict(session)


@router.post("/sessions")
async def create_session(
    request: Request,
    body: CreateSessionRequest,
    x_api_key: str | None = Header(None),
) -> dict:
    """Create a new deploy session."""
    check_auth(request, x_api_key)
    svc = request.app.state.deploy
    if not svc:
        return {"error": "deploy not configured"}
    session = svc.create_session(
        project=body.project,
        branch=body.branch,
    )
    return asdict(session)
