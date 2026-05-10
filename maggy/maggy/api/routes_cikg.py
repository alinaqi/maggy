"""CIKG REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from .auth import check_auth

router = APIRouter(prefix="/api/cikg", tags=["cikg"])


@router.get("/landscape")
async def landscape(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Return competitive landscape summary."""
    check_auth(request, x_api_key)
    graph = request.app.state.cikg
    if not graph:
        return {"error": "cikg not configured"}
    from maggy.cikg.queries import get_landscape
    return get_landscape(graph)


@router.get("/gaps/{feature}")
async def feature_gaps(
    request: Request,
    feature: str,
    x_api_key: str | None = Header(None),
) -> dict:
    """Score a feature against competitive landscape."""
    check_auth(request, x_api_key)
    graph = request.app.state.cikg
    if not graph:
        return {"error": "cikg not configured"}
    from maggy.cikg.queries import find_gaps
    from dataclasses import asdict
    return asdict(find_gaps(graph, feature))
