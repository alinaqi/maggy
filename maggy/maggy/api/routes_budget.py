"""Budget REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from .auth import check_auth, require_configured

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.get("")
async def get_budget(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Return current budget status."""
    check_auth(request, x_api_key)
    budget = request.app.state.budget
    if not budget:
        return {"status": "unconfigured"}
    return budget.budget_status()


@router.get("/by-provider")
async def by_provider(
    request: Request,
    x_api_key: str | None = Header(None),
) -> list[dict]:
    """Return spend breakdown by provider."""
    check_auth(request, x_api_key)
    budget = request.app.state.budget
    if not budget:
        return []
    return budget.by_provider()
