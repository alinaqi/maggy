"""Shared authentication and configuration guards."""

from __future__ import annotations

from fastapi import HTTPException, Request


def check_auth(
    request: Request, x_api_key: str | None,
) -> None:
    """Simple token check. Bypassed when auth_mode='local'."""
    cfg = request.app.state.cfg
    if cfg.dashboard.auth_mode == "local":
        return
    expected = cfg.dashboard.api_key
    if not expected or x_api_key != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-API-Key",
        )


def require_configured(request: Request) -> None:
    """Abort 503 if Maggy is not configured."""
    if not getattr(request.app.state, "configured", False):
        raise HTTPException(
            status_code=503,
            detail="Maggy is not configured yet.",
        )


def require_provider(request: Request) -> None:
    """Abort 503 if no provider credentials (Tier 2)."""
    mode = getattr(request.app.state, "mode", "local")
    if mode != "full":
        raise HTTPException(
            status_code=503,
            detail="Provider credentials required. "
            "Set GITHUB_TOKEN or configure Asana.",
        )
