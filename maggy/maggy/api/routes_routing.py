"""Routing REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Header, Request

from .auth import check_auth

router = APIRouter(prefix="/api/routing", tags=["routing"])


@router.get("/heatmap")
async def heatmap(
    request: Request,
    x_api_key: str | None = Header(None),
) -> list[dict]:
    """Return reward heatmap for dashboard."""
    check_auth(request, x_api_key)
    svc = request.app.state.routing
    if not svc:
        return []
    return svc.get_heatmap()


@router.get("/decide")
async def decide(
    request: Request,
    blast: int = 0,
    task_type: str = "general",
    security: bool = False,
    fatigue: float = 0.0,
    x_api_key: str | None = Header(None),
) -> dict:
    """Get routing decision for given context."""
    check_auth(request, x_api_key)
    svc = request.app.state.routing
    if not svc:
        return {"error": "routing not configured"}
    from maggy.routing import RoutingContext
    ctx = RoutingContext(blast, task_type, security, fatigue_score=fatigue)
    decision = svc.route(ctx)
    return {
        "primary": decision.primary,
        "validator": decision.validator,
        "fallback": decision.fallback_chain,
        "reason": decision.reason,
    }


@router.get("/rules")
async def rules(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict:
    """Return full routing rules summary."""
    check_auth(request, x_api_key)
    svc = request.app.state.routing
    if not svc:
        return {"mode": "unconfigured"}
    return _serialize_rules(svc.rules, svc.cfg.routing.mode)


def _serialize_rules(r, mode: str) -> dict:
    """Serialize RoutingRules to API response."""
    return {
        "mode": mode,
        "task_type_overrides": _ser_overrides(r.task_type_overrides),
        "pipeline_phases": _ser_overrides(r.pipeline_phases),
        "model_performance": _ser_perf(r.model_performance),
        "conventions": [
            {"text": c.text, "applies_to": c.applies_to, "source": c.source}
            for c in r.conventions
        ],
        "stakes": _ser_stakes(r.stakes),
        "cascade": {
            "enabled": r.cascade.enabled,
            "min_blast": r.cascade.min_blast,
            "min_stakes": r.cascade.min_stakes,
            "max_attempts": r.cascade.max_attempts,
            "quality_threshold": r.cascade.quality_threshold,
        },
    }


def _ser_overrides(overrides: dict) -> dict:
    """Serialize ModelOverride dict."""
    return {
        k: {
            "model": v.model, "reason": v.reason,
            "confidence": v.confidence, "source": v.source,
        }
        for k, v in overrides.items()
    }


def _ser_perf(perf: dict) -> dict:
    """Serialize PerformanceRecord dict."""
    return {
        k: {
            "strengths": v.strengths,
            "weaknesses": v.weaknesses,
            "success_rate": v.success_rate,
            "tasks_completed": v.tasks_completed,
        }
        for k, v in perf.items()
    }


def _ser_stakes(stakes) -> dict:
    """Serialize StakesPatterns."""
    def _level(lv):
        return {
            "file_patterns": lv.file_patterns,
            "task_types": lv.task_types,
            "keywords": lv.keywords,
        }
    return {
        "high": _level(stakes.high),
        "medium": _level(stakes.medium),
        "low": _level(stakes.low),
    }
