"""One-click srooter routing from the dashboard.

Thin wrapper over `maggy.services.srooter`, which shells out to `srooterctl`.
Loopback-only dashboard (auth_mode=local) means these privileged local actions
are safe; token mode still enforces X-API-Key via check_auth.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from maggy.api.auth import check_auth
from maggy.services import srooter

router = APIRouter(prefix="/api/srooter", tags=["srooter"])


class EnableRequest(BaseModel):
    api_key: str
    gateway_url: str = ""


@router.get("/status")
async def srooter_status(
    request: Request, x_api_key: str | None = Header(None),
) -> dict:
    """Is routing through srooter on? Plus key/gateway/shell state."""
    check_auth(request, x_api_key)
    return srooter.status()


@router.post("/enable")
async def srooter_enable(
    request: Request, body: EnableRequest, x_api_key: str | None = Header(None),
) -> dict:
    """Wire srooter routing with a single key. Returns the fresh status."""
    check_auth(request, x_api_key)
    try:
        return srooter.enable(body.api_key, body.gateway_url)
    except FileNotFoundError:
        raise HTTPException(503, "srooterctl not installed")
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@router.post("/disable")
async def srooter_disable(
    request: Request, x_api_key: str | None = Header(None),
) -> dict:
    """Revert to direct Anthropic routing. Returns the fresh status."""
    check_auth(request, x_api_key)
    try:
        return srooter.disable()
    except FileNotFoundError:
        raise HTTPException(503, "srooterctl not installed")
