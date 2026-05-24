"""Pipeline log REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, Query, Request

from .auth import check_auth

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

_EMPTY_STATS: dict = {
    "total_calls": 0, "total_cost": 0.0,
    "avg_latency_ms": 0.0, "success_rate": 0.0,
    "by_model": [],
}


@router.get("/logs")
async def get_logs(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    session_id: str | None = Query(None),
    model: str | None = Query(None),
    x_api_key: str | None = Header(None),
) -> list[dict]:
    check_auth(request, x_api_key)
    store = getattr(request.app.state, "pipeline_log_store", None)
    if not store:
        return []
    return store.recent(
        limit=limit, session_id=session_id, model=model,
    )


@router.get("/stats")
async def get_stats(
    request: Request,
    period: str = Query("today"),
    x_api_key: str | None = Header(None),
) -> dict:
    check_auth(request, x_api_key)
    store = getattr(request.app.state, "pipeline_log_store", None)
    if not store:
        return _EMPTY_STATS
    return store.stats(period)
