"""Model health + council config + model CRUD API routes."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request
from pydantic import BaseModel

from maggy.services.model_registry import (
    add_model as add_model_registry,
    list_models as list_models_registry,
    remove_model as remove_model_registry,
    validate_model as validate_model_registry,
)

from .auth import check_auth

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models")
async def list_models(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """List all configured AI models with custom flag."""
    check_auth(request, x_api_key)
    models = list_models_registry()
    return {"models": models, "total": len(models)}


class _AddModelBody(BaseModel):
    model_id: str
    label: str
    access_type: str
    cli_cmd: str = ""
    api_key: str = ""
    api_base: str = ""
    tier: int = 99


@router.post("/models")
async def add_model(
    body: _AddModelBody,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Add a custom AI model."""
    check_auth(request, x_api_key)
    return add_model_registry(
        model_id=body.model_id,
        label=body.label,
        access_type=body.access_type,
        cli_cmd=body.cli_cmd,
        api_key=body.api_key,
        api_base=body.api_base,
        tier=body.tier,
    )


@router.delete("/models/{model_id}")
async def remove_model(
    model_id: str,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Remove a custom AI model."""
    check_auth(request, x_api_key)
    return remove_model_registry(model_id)


class _ValidateBody(BaseModel):
    access_type: str
    cli_cmd: str = ""
    api_key: str = ""
    api_base: str = ""


@router.post("/models/check/validate")
async def validate_model(
    body: _ValidateBody,
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Validate a model before adding."""
    check_auth(request, x_api_key)
    return validate_model_registry(
        access_type=body.access_type,
        cli_cmd=body.cli_cmd,
        api_key=body.api_key,
        api_base=body.api_base,
    )


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
