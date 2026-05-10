"""Engram REST endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, Request

from .auth import check_auth

router = APIRouter(prefix="/api/engram", tags=["engram"])


@router.get("/query")
async def query_engrams(
    request: Request,
    namespace: str | None = None,
    memory_type: str | None = None,
    limit: int = 50,
    x_api_key: str | None = Header(None),
) -> dict:
    """Query engram records."""
    check_auth(request, x_api_key)
    engram = request.app.state.engram
    if not engram:
        return {"error": "engram not configured"}
    records = engram.query(
        namespace=namespace,
        memory_type=memory_type,
        limit=limit,
    )
    return {"records": [asdict(r) for r in records]}


@router.get("/diagnostics")
async def diagnostics(
    request: Request,
    namespace: str | None = None,
    x_api_key: str | None = Header(None),
) -> dict:
    """Run memory diagnostics."""
    check_auth(request, x_api_key)
    store = request.app.state.engram
    if not store:
        return {"error": "engram not configured"}
    from maggy.engram.diagnostics import diagnose
    profile = diagnose(store, namespace)
    return asdict(profile)
