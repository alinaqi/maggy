"""Observability signal REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from .auth import check_auth

router = APIRouter(
    prefix="/api/observability", tags=["observability"],
)


class _SignalIn(BaseModel):
    project: str
    signal_type: str
    value: float


@router.get("/signals/{project}")
async def get_signals(
    project: str,
    request: Request,
    x_api_key: str | None = Header(None),
    limit: int = 20,
) -> list[dict]:
    """Get recent signals for a project."""
    check_auth(request, x_api_key)
    obs = request.app.state.observability
    if not obs:
        return []
    return obs.recent_signals(project, min(limit, 100))


@router.post("/record", status_code=201)
async def record_signal(
    body: _SignalIn,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Record an observability signal."""
    check_auth(request, x_api_key)
    obs = request.app.state.observability
    if not obs:
        raise HTTPException(503, "Not configured")
    obs.record_signal(body.project, body.signal_type, body.value)
    return {"status": "recorded"}
