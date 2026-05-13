"""Blueprint API routes."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request

from maggy.api.auth import check_auth

router = APIRouter(prefix="/api/blueprints", tags=["blueprints"])


def _require_store(request: Request):
    store = getattr(request.app.state, "blueprints", None)
    if store is None:
        raise HTTPException(503, "Blueprint store not configured")
    return store


@router.get("/")
async def list_blueprints(
    request: Request,
    x_api_key: str | None = Header(None),
):
    """List all stored blueprints."""
    check_auth(request, x_api_key)
    store = _require_store(request)
    return store.list_all()


@router.get("/match")
async def match_blueprint(
    request: Request,
    task_type: str = "general",
    keywords: str = "",
    x_api_key: str | None = Header(None),
):
    """Find matching blueprint for task type + keywords."""
    check_auth(request, x_api_key)
    store = _require_store(request)
    kw = [k.strip() for k in keywords.split(",") if k.strip()]
    result = store.match(task_type, kw)
    return {"match": result}
