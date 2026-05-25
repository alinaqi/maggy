"""Model health + council config API routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from .auth import check_auth

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
async def list_models(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """List all configured AI models with tiers."""
    check_auth(request, x_api_key)
    from maggy.services.council_config import load_council_config
    cfg = load_council_config()
    return {
        "models": [m.to_dict() for m in cfg.models],
        "total": len(cfg.models),
    }


@router.post("/models/health")
async def check_all_health(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Ping all models in parallel, return health status."""
    check_auth(request, x_api_key)
    from maggy.services.council_config import load_council_config
    from maggy.services.model_health import check_all_models
    cfg = load_council_config()
    results = check_all_models(cfg.models, timeout=15)
    return {
        "results": [
            {
                "model_id": r.model_id,
                "success": r.success,
                "latency_ms": r.latency_ms,
                "output": r.output[:100] if r.output else "",
                "error": r.error,
            }
            for r in results
        ],
        "healthy": sum(1 for r in results if r.success),
        "total": len(results),
    }


@router.post("/models/{model_id}/health")
async def check_single_health(
    model_id: str,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Ping a single model."""
    check_auth(request, x_api_key)
    from maggy.services.council_config import load_council_config
    from maggy.services.model_health import check_model_health
    cfg = load_council_config()
    model = cfg.get_model(model_id)
    if not model:
        return {"model_id": model_id, "success": False, "error": "Unknown model"}
    argv = model.cmd_argv()
    if not argv:
        return {"model_id": model_id, "success": False, "error": "No command configured"}
    result = check_model_health(model_id, argv, timeout=15)
    return {
        "model_id": result.model_id,
        "success": result.success,
        "latency_ms": result.latency_ms,
        "output": result.output[:100] if result.output else "",
        "error": result.error,
    }


@router.get("/council/config")
async def get_council_config(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Return council of experts configuration."""
    check_auth(request, x_api_key)
    from maggy.services.council_config import load_council_config
    cfg = load_council_config()
    return cfg.to_dict()


class _CouncilUpdate(BaseModel):
    enabled: bool | None = None
    threshold: int | None = None
    auto_validate_plans: bool | None = None
    auto_review_architecture: bool | None = None
    auto_review_prs: bool | None = None


@router.patch("/council/config")
async def update_council_config(
    body: _CouncilUpdate,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Update council configuration."""
    check_auth(request, x_api_key)
    from maggy.services.council_config import load_council_config, save_council_config
    cfg = load_council_config()
    if body.enabled is not None:
        cfg.enabled = body.enabled
    if body.threshold is not None:
        cfg.threshold = max(1, min(body.threshold, 10))
    if body.auto_validate_plans is not None:
        cfg.auto_validate_plans = body.auto_validate_plans
    if body.auto_review_architecture is not None:
        cfg.auto_review_architecture = body.auto_review_architecture
    if body.auto_review_prs is not None:
        cfg.auto_review_prs = body.auto_review_prs
    save_council_config(cfg)
    return {"ok": True, **cfg.to_dict()}
