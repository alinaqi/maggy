"""REST endpoints for approval flow — inbox review channel."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/approval", tags=["approval"])


@router.get("/pending")
async def get_pending(request: Request) -> dict:
    store = getattr(request.app.state, "approval_store", None)
    if not store:
        return {"items": []}
    items = store.pending()
    return {"items": [_serialize(r) for r in items]}


@router.get("/history")
async def get_history(request: Request, limit: int = 50) -> dict:
    store = getattr(request.app.state, "approval_store", None)
    if not store:
        return {"items": []}
    items = store.history(limit=limit)
    return {"items": [_serialize(r) for r in items]}


@router.post("/{request_id}/approve")
async def approve(request_id: str, request: Request) -> dict:
    store = getattr(request.app.state, "approval_store", None)
    if not store:
        raise HTTPException(404, "Approval store not initialized")
    existing = store.get(request_id)
    if not existing:
        raise HTTPException(404, "Approval request not found")
    store.resolve(request_id, "approved", "human")
    return {"status": "approved", "id": request_id}


@router.post("/{request_id}/reject")
async def reject(request_id: str, request: Request) -> dict:
    store = getattr(request.app.state, "approval_store", None)
    if not store:
        raise HTTPException(404, "Approval store not initialized")
    existing = store.get(request_id)
    if not existing:
        raise HTTPException(404, "Approval request not found")
    store.resolve(request_id, "rejected", "human")
    return {"status": "rejected", "id": request_id}


def _serialize(req) -> dict:
    return {
        "id": req.id,
        "action": req.action,
        "risk": req.risk,
        "context": req.context,
        "status": req.status,
        "created_at": req.created_at,
        "resolved_at": req.resolved_at,
        "resolved_by": req.resolved_by,
    }
