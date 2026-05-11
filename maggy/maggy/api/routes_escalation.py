"""Escalation REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from .auth import check_auth

router = APIRouter(prefix="/api/escalations", tags=["escalations"])


class _EscalationIn(BaseModel):
    session_id: str
    reason: str
    context: dict = {}


class _ResolveIn(BaseModel):
    guidance: str


@router.get("")
async def list_pending(
    request: Request,
    x_api_key: str | None = Header(None),
) -> list[dict]:
    """List pending escalations."""
    check_auth(request, x_api_key)
    esc = request.app.state.escalator
    if not esc:
        return []
    return [
        {
            "id": p.id, "session_id": p.session_id,
            "reason": p.reason, "created_at": p.created_at,
        }
        for p in esc.list_pending()
    ]


@router.post("", status_code=201)
async def create_escalation(
    body: _EscalationIn,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Create a new escalation."""
    check_auth(request, x_api_key)
    esc = request.app.state.escalator
    if not esc:
        raise HTTPException(503, "Not configured")
    packet = esc.escalate(
        body.session_id, body.reason, body.context,
    )
    return {"id": packet.id, "status": "pending"}


@router.post("/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: str,
    body: _ResolveIn,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Resolve an escalation with guidance."""
    check_auth(request, x_api_key)
    esc = request.app.state.escalator
    if not esc:
        raise HTTPException(503, "Not configured")
    try:
        packet = esc.resolve(escalation_id, body.guidance)
    except KeyError:
        raise HTTPException(404, "Not found")
    return {"id": packet.id, "status": "resolved"}
