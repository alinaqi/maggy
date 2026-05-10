"""Routing REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from .auth import check_auth

router = APIRouter(prefix="/api/routing", tags=["routing"])


@router.get("/heatmap")
async def heatmap(
    request: Request,
    x_api_key: str | None = Header(None),
) -> list[dict]:
    """Return reward heatmap for dashboard."""
    check_auth(request, x_api_key)
    svc = request.app.state.routing
    if not svc:
        return []
    return svc.get_heatmap()


@router.get("/decide")
async def decide(
    request: Request,
    blast: int = 0,
    task_type: str = "general",
    security: bool = False,
    x_api_key: str | None = Header(None),
) -> dict:
    """Get routing decision for given context."""
    check_auth(request, x_api_key)
    svc = request.app.state.routing
    if not svc:
        return {"error": "routing not configured"}
    from maggy.routing import RoutingContext
    ctx = RoutingContext(blast, task_type, security)
    decision = svc.route(ctx)
    return {
        "primary": decision.primary,
        "validator": decision.validator,
        "fallback": decision.fallback_chain,
        "reason": decision.reason,
    }
