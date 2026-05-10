"""Forge REST endpoints."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel, Field

from .auth import check_auth

router = APIRouter(prefix="/api/forge", tags=["forge"])


class GapReport(BaseModel):
    capability: str = Field(..., min_length=1, max_length=200)


@router.get("/status")
async def forge_status(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Return Forge connector status."""
    check_auth(request, x_api_key)
    forge = request.app.state.forge
    if not forge:
        return {"error": "forge not configured"}
    return asdict(forge.status())


@router.get("/search")
async def search_tools(
    request: Request,
    q: str = "",
    x_api_key: str | None = Header(None),
) -> dict:
    """Search the Forge tool registry."""
    check_auth(request, x_api_key)
    forge = request.app.state.forge
    if not forge:
        return {"error": "forge not configured"}
    return {"results": forge.search_tools(q)}


@router.get("/gaps")
async def list_gaps(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """List detected capability gaps."""
    check_auth(request, x_api_key)
    forge = request.app.state.forge
    if not forge:
        return {"error": "forge not configured"}
    return {"gaps": forge.get_gaps()}


@router.post("/gaps")
async def report_gap(
    request: Request,
    body: GapReport,
    x_api_key: str | None = Header(None),
) -> dict:
    """Report a capability gap."""
    check_auth(request, x_api_key)
    forge = request.app.state.forge
    if not forge:
        return {"error": "forge not configured"}
    return forge.report_gap(body.capability)
