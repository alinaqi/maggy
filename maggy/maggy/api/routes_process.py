"""Process Intelligence REST routes — /api/process/*."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/process", tags=["process"])


def _auth(request: Request, x_api_key: str | None) -> None:
    cfg = request.app.state.cfg
    if cfg.dashboard.auth_mode == "local":
        return
    expected = cfg.dashboard.api_key
    if not expected or x_api_key != expected:
        raise HTTPException(401, "Invalid or missing X-API-Key")


def _require_process(request: Request) -> None:
    if not getattr(request.app.state, "process", None):
        raise HTTPException(503, "Process Intelligence not configured")


class AnalyzeRequest(BaseModel):
    project_key: str


@router.post("/analyze")
async def analyze(
    request: Request,
    body: AnalyzeRequest,
    x_api_key: str | None = Header(None),
) -> dict:
    """Trigger full PR analysis (background)."""
    _auth(request, x_api_key)
    _require_process(request)
    svc = request.app.state.process

    try:
        report = await svc.analyze(body.project_key)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Analysis failed for %s", body.project_key)
        raise HTTPException(502, f"Analysis failed: {e}")

    return {
        "status": "completed",
        "project_key": body.project_key,
        "total_prs": report.total_prs,
        "summary": report.summary,
    }


@router.get("/report/{project_key}")
async def get_report(
    request: Request,
    project_key: str,
    x_api_key: str | None = Header(None),
) -> dict:
    """Get latest process report."""
    _auth(request, x_api_key)
    _require_process(request)
    report = request.app.state.process.get_report(project_key)
    if not report:
        raise HTTPException(404, "No report found. Run /api/process/analyze first.")
    return report


@router.get("/health/{project_key}")
async def get_health(
    request: Request,
    project_key: str,
    x_api_key: str | None = Header(None),
) -> dict:
    """Get process health metrics."""
    _auth(request, x_api_key)
    _require_process(request)
    health = request.app.state.process.get_health(project_key)
    if not health:
        raise HTTPException(404, "No health data. Run /api/process/analyze first.")
    return health
