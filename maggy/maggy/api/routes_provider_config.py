"""Provider config REST endpoints — read and update routing.yaml via API."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from .auth import check_auth
from maggy.provider_config import (
    ProviderConfig,
    load_provider_config,
    save_provider_config,
    SOVEREIGNTY_BLOCKED,
)

router = APIRouter(prefix="/api/routing/provider-config", tags=["provider-config"])


class ProviderConfigUpdate(BaseModel):
    sovereignty: str | None = None
    tiers: dict[str, str] | None = None


@router.get("")
async def get_config(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Return current provider config and available options."""
    check_auth(request, x_api_key)
    cfg = load_provider_config()
    return {
        "config": cfg.to_dict(),
        "flash_bin": cfg.flash_bin(),
        "pro_bin": cfg.pro_bin(),
        "options": {
            "sovereignty": ["us", "local", "any"],
            "flash": ["groq", "together", "ollama", "deepseek"],
            "pro": ["together", "groq", "ollama", "deepseek"],
        },
        "sovereignty_blocked": {k: list(v) for k, v in SOVEREIGNTY_BLOCKED.items()},
    }


@router.post("")
async def update_config(
    request: Request,
    body: ProviderConfigUpdate,
    x_api_key: str | None = Header(None),
) -> dict:
    """Update provider config and persist to ~/.maggy/routing.yaml."""
    check_auth(request, x_api_key)

    cfg = load_provider_config()

    if body.sovereignty is not None:
        if body.sovereignty not in ("us", "local", "any"):
            raise HTTPException(status_code=400, detail="sovereignty must be us, local, or any")
        cfg.sovereignty = body.sovereignty
        # Re-init tiers for new sovereignty
        from maggy.provider_config import _SOVEREIGNTY_TIER_DEFAULTS, _US_FALLBACK
        defaults = _SOVEREIGNTY_TIER_DEFAULTS.get(cfg.sovereignty, _US_FALLBACK)
        for tier, provider in defaults.items():
            cfg.tiers[tier] = provider

    if body.tiers is not None:
        for tier, provider in body.tiers.items():
            if not cfg.is_allowed(provider):
                raise HTTPException(
                    status_code=400,
                    detail=f"Provider '{provider}' is blocked by sovereignty={cfg.sovereignty}",
                )
            cfg.tiers[tier] = provider

    save_provider_config(cfg)
    return {"ok": True, "config": cfg.to_dict()}
