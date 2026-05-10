"""Self-improvement API routes — reports and manual analysis."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, HTTPException, Request

from maggy.api.auth import check_auth

router = APIRouter(prefix="/api", tags=["improve"])


@router.get("/improve/report")
async def get_report(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    check_auth(request, x_api_key)
    introspector = getattr(request.app.state, "introspector", None)
    if not introspector:
        raise HTTPException(status_code=503, detail="Not configured")
    report = introspector.get_report()
    if not report:
        return {"report": None}
    return {"report": asdict(report)}


@router.post("/improve/analyze")
async def run_analysis(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    check_auth(request, x_api_key)
    introspector = getattr(request.app.state, "introspector", None)
    if not introspector:
        raise HTTPException(status_code=503, detail="Not configured")
    report = introspector.analyze()
    return {"report": asdict(report)}
