"""Event Spine REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from .auth import check_auth

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def query_events(
    request: Request,
    task_id: str | None = None,
    event_type: str | None = None,
    project_id: str | None = None,
    limit: int = 100,
    x_api_key: str | None = Header(None),
) -> list[dict]:
    """Query events with optional filters."""
    check_auth(request, x_api_key)
    emitter = request.app.state.events
    if not emitter:
        return []
    return emitter.query(task_id, event_type, project_id, limit)


@router.get("/trace/{task_id}")
async def trace_task(
    request: Request,
    task_id: str,
    x_api_key: str | None = Header(None),
) -> list[dict]:
    """Get full event chain for a task."""
    check_auth(request, x_api_key)
    emitter = request.app.state.events
    if not emitter:
        return []
    return emitter.trace(task_id)


@router.get("/count")
async def count_events(
    request: Request,
    event_type: str | None = None,
    project_id: str | None = None,
    x_api_key: str | None = Header(None),
) -> dict:
    """Count events matching filters."""
    check_auth(request, x_api_key)
    emitter = request.app.state.events
    if not emitter:
        return {"count": 0}
    return {"count": emitter.count(event_type, project_id)}
