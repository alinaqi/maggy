"""Heartbeat API routes — scheduler status and manual triggers."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from maggy.api.auth import check_auth

router = APIRouter(prefix="/api", tags=["heartbeat"])


@router.get("/heartbeat/status")
async def heartbeat_status(
    request: Request,
    x_api_key: str | None = Header(None),
) -> list[dict]:
    check_auth(request, x_api_key)
    scheduler = getattr(request.app.state, "heartbeat", None)
    if not scheduler:
        return []
    return scheduler.status()


@router.post("/heartbeat/trigger/{job_name}")
async def trigger_job(
    request: Request,
    job_name: str,
    x_api_key: str | None = Header(None),
) -> dict:
    check_auth(request, x_api_key)
    scheduler = getattr(request.app.state, "heartbeat", None)
    if not scheduler:
        raise HTTPException(status_code=503, detail="Heartbeat not running")
    try:
        return await scheduler.trigger(job_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Job '{job_name}' not found")
