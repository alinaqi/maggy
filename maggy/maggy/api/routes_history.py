"""API routes for session history analysis."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from maggy.api.auth import check_auth

router = APIRouter(
    prefix="/api/history", tags=["history"],
)


def _require_history(request: Request):
    svc = getattr(request.app.state, "history", None)
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="History service not available.",
        )
    return svc


@router.post("/analyze")
async def analyze_history(
    request: Request,
    x_api_key: str | None = Header(None),
):
    """Trigger full history analysis pipeline."""
    check_auth(request, x_api_key)
    svc = _require_history(request)
    report = svc.analyze()
    return {
        "status": "ok",
        "total_sessions": report.total_sessions,
        "total_prompts": report.total_prompts,
        "providers": len(report.providers),
        "patterns": report.patterns,
        "summary": report.summary,
    }


@router.get("/report")
async def get_report(
    request: Request,
    x_api_key: str | None = Header(None),
):
    """Get latest cached history report."""
    check_auth(request, x_api_key)
    svc = _require_history(request)
    report = svc.get_report()
    if not report:
        return {"status": "no_data"}
    return report


@router.get("/sessions")
async def get_sessions(
    request: Request,
    provider: str | None = None,
    x_api_key: str | None = Header(None),
):
    """Get parsed session records."""
    check_auth(request, x_api_key)
    svc = _require_history(request)
    sessions = svc.get_sessions(provider=provider)
    return {"sessions": sessions, "total": len(sessions)}


@router.get("/providers")
async def list_providers(
    request: Request,
    x_api_key: str | None = Header(None),
):
    """List which CLI tools are available."""
    check_auth(request, x_api_key)
    svc = _require_history(request)
    return {"providers": svc.available_providers()}
