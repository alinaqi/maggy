"""Mesh P2P REST endpoints — admin operations."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from .auth import check_auth

router = APIRouter(prefix="/api/mesh", tags=["mesh"])


@router.post("/announce")
async def announce(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Announce self to all org mesh repos via git."""
    check_auth(request, x_api_key)
    mesh = request.app.state.mesh
    if not mesh:
        return JSONResponse(
            {"error": "mesh not enabled"}, status_code=503,
        )
    cfg = request.app.state.cfg
    token = cfg.issue_tracker.github.token
    if not token:
        return JSONResponse(
            {"error": "no github token"}, status_code=422,
        )
    result = await mesh.announce_all(token)
    return {"announced": result}


@router.post("/discover")
async def discover(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Trigger git-based peer discovery for all orgs."""
    check_auth(request, x_api_key)
    mesh = request.app.state.mesh
    if not mesh:
        return JSONResponse(
            {"error": "mesh not enabled"}, status_code=503,
        )
    cfg = request.app.state.cfg
    token = cfg.issue_tracker.github.token
    if not token:
        return JSONResponse(
            {"error": "no github token"}, status_code=422,
        )
    result = await mesh.discover(token)
    return {"discovered": result}


@router.post("/setup")
async def setup(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Onboarding: create mesh repos for all orgs."""
    check_auth(request, x_api_key)
    mesh = request.app.state.mesh
    if not mesh:
        return JSONResponse(
            {"error": "mesh not enabled"}, status_code=503,
        )
    cfg = request.app.state.cfg
    token = cfg.issue_tracker.github.token
    if not token:
        return JSONResponse(
            {"error": "no github token"}, status_code=422,
        )
    result = await mesh.setup_repos(token)
    return {"repos_created": result}
