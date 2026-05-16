"""Unified usage analytics API — cross-model stats."""

from __future__ import annotations

from fastapi import APIRouter, Query

from maggy.services.usage_analytics import generate_report

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("/report")
async def usage_report(period: str = Query("today", regex="^(today|week|month|all)$")):
    """Cross-model usage report for the given period."""
    report = generate_report(period)
    return {
        "period": report.period,
        "generated_at": report.generated_at,
        "routing_decisions": report.routing_decisions,
        "top_classifier": report.top_classifier,
        "total_cost": round(report.total_cost, 4),
        "savings_vs_claude": round(report.savings_vs_claude, 2),
        "fatigue_avg": round(report.fatigue_avg, 2),
        "fatigue_peak": round(report.fatigue_peak, 2),
        "total_calls": report.total_calls,
        "total_tokens": report.total_tokens,
        "models": [
            {
                "model": m.model,
                "calls": m.calls,
                "tokens": m.tokens_in + m.tokens_out,
                "cost_est": round(m.cost_est, 4),
            }
            for m in report.models
        ],
    }
