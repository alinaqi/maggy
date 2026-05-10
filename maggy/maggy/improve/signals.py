"""Signal collectors — pull data from existing services."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import SignalBundle

MIN_SAMPLES = 5
LOW_REWARD = 0.4
HIGH_FAILURE_RATE = 0.2
LOW_USAGE_RATE = 0.05


def collect_routing(routing) -> dict:
    """Read reward heatmap from RoutingService."""
    heatmap = routing.get_heatmap()
    underperformers = [
        entry for entry in heatmap
        if entry.get("count", 0) >= MIN_SAMPLES
        and entry.get("avg_reward", 1.0) < LOW_REWARD
    ]
    return {"heatmap": heatmap, "underperformers": underperformers}


def collect_events(events) -> dict:
    """Read outcome events for failure analysis."""
    outcomes = events.query(event_type="outcome", limit=200)
    total = len(outcomes)
    failures = sum(
        1 for o in outcomes
        if not o.get("success", True)
    )
    rate = failures / total if total else 0.0
    return {
        "total": total,
        "failures": failures,
        "failure_rate": round(rate, 3),
    }


def collect_history(history) -> dict:
    """Read session patterns from HistoryService."""
    report = history.get_report()
    if not report:
        return {"sessions": 0, "patterns": []}
    return {
        "sessions": report.get("total_sessions", 0),
        "patterns": report.get("patterns", []),
        "by_provider": report.get("by_provider", {}),
    }


def collect_forge(forge) -> dict:
    """Read capability gaps from ForgeConnector."""
    gaps = forge.get_gaps()
    return {"gaps": gaps, "count": len(gaps)}


def collect_engram(engram) -> dict:
    """Read memory health from EngramStore."""
    from maggy.engram.diagnostics import diagnose
    profile = diagnose(engram)
    return {
        "health_score": profile.health_score,
        "total": profile.total_memories,
        "active": profile.active_count,
        "superseded": profile.superseded_count,
    }


def collect_budget(budget) -> dict:
    """Read spend patterns from BudgetManager."""
    return budget.budget_status()


def collect_all(app_state) -> SignalBundle:
    """Collect signals from all available services."""
    bundle = SignalBundle(
        collected_at=datetime.now(timezone.utc).isoformat(),
    )
    if app_state.routing:
        bundle.routing = collect_routing(app_state.routing)
    if app_state.events:
        bundle.events = collect_events(app_state.events)
    if app_state.history:
        bundle.history = collect_history(app_state.history)
    if app_state.forge:
        bundle.forge = collect_forge(app_state.forge)
    if app_state.engram:
        bundle.engram = collect_engram(app_state.engram)
    if app_state.budget:
        bundle.budget = collect_budget(app_state.budget)
    return bundle
