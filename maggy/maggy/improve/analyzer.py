"""Analyze collected signals and produce recommendations."""

from __future__ import annotations

from .models import Recommendation, SignalBundle

LOW_REWARD = 0.4
HIGH_FAILURE_RATE = 0.2
LOW_USAGE_RATE = 0.05
LOW_HEALTH = 0.5
HIGH_UTILIZATION = 0.9


def analyze_routing(signals: SignalBundle) -> list[Recommendation]:
    """Flag models with low average reward."""
    recs: list[Recommendation] = []
    for entry in signals.routing.get("underperformers", []):
        recs.append(Recommendation(
            category="routing",
            severity="warning",
            message=(
                f"Model {entry.get('model', '?')} underperforms on "
                f"{entry.get('task_type', '?')} "
                f"(avg reward {entry.get('avg_reward', 0):.2f})."
            ),
            suggestion="Consider routing to a different model.",
            data=entry,
        ))
    return recs


def analyze_failures(signals: SignalBundle) -> list[Recommendation]:
    """Flag high execution failure rates."""
    rate = signals.events.get("failure_rate", 0)
    if rate < HIGH_FAILURE_RATE:
        return []
    return [Recommendation(
        category="reliability",
        severity="action",
        message=f"Execution failure rate is {rate:.0%}.",
        suggestion="Check tool configuration and logs.",
        data=signals.events,
    )]


def analyze_usage(signals: SignalBundle) -> list[Recommendation]:
    """Detect underutilized providers."""
    recs: list[Recommendation] = []
    by_provider = signals.history.get("by_provider", {})
    total = signals.history.get("sessions", 0)
    if total == 0:
        return []
    for provider, count in by_provider.items():
        ratio = count / total
        if ratio < LOW_USAGE_RATE:
            recs.append(Recommendation(
                category="usage",
                severity="info",
                message=(
                    f"{provider} used in only "
                    f"{ratio:.0%} of sessions."
                ),
                suggestion="Consider removing or promoting it.",
                data={"provider": provider, "ratio": ratio},
            ))
    return recs


def analyze_gaps(signals: SignalBundle) -> list[Recommendation]:
    """Surface triggered capability gaps."""
    recs: list[Recommendation] = []
    for gap in signals.forge.get("gaps", []):
        recs.append(Recommendation(
            category="capability",
            severity="action",
            message=(
                f"Capability '{gap.get('name', '?')}' "
                f"requested {gap.get('count', 0)} times."
            ),
            suggestion="Consider building an MCP server.",
            data=gap,
        ))
    return recs


def analyze_memory(signals: SignalBundle) -> list[Recommendation]:
    """Flag low engram health scores."""
    score = signals.engram.get("health_score", 1.0)
    if score >= LOW_HEALTH:
        return []
    return [Recommendation(
        category="memory",
        severity="warning",
        message=f"Memory health is {score:.2f}.",
        suggestion="Run engram cleanup or review superseded records.",
        data=signals.engram,
    )]


def analyze_cost(signals: SignalBundle) -> list[Recommendation]:
    """Flag high budget utilization."""
    util = signals.budget.get("utilization", 0)
    if util < HIGH_UTILIZATION:
        return []
    return [Recommendation(
        category="cost",
        severity="action",
        message=f"Budget utilization at {util:.0%}.",
        suggestion="Increase daily_limit_usd or optimize routing.",
        data=signals.budget,
    )]


def analyze_all(signals: SignalBundle) -> list[Recommendation]:
    """Run all analyzers and merge results."""
    recs: list[Recommendation] = []
    for fn in (
        analyze_routing, analyze_failures, analyze_usage,
        analyze_gaps, analyze_memory, analyze_cost,
    ):
        recs.extend(fn(signals))
    return recs
