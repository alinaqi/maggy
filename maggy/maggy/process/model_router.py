"""Dynamic model routing — routes tasks to models by complexity.

Not just fallback chains: intelligent routing based on task complexity,
security sensitivity, and task type. Simple tasks go to cheap models,
complex tasks to premium, security-critical get dual validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from maggy.mnemos.constants import (
    FATIGUE_ROUTING_ESCALATE as _ESCALATE,
    FATIGUE_ROUTING_PREMIUM as _REM,
)

from .models import ModelTier


DEFAULT_TIERS: list[ModelTier] = [
    ModelTier(
        name="local",
        provider="ollama",
        model="qwen3-coder:30b-a3b-q8_0",
        cost_rank=1,
        complexity_min=0,
        complexity_max=3,
        strengths=["formatting", "simple_edits", "crud"],
    ),
    ModelTier(
        name="deepseek-flash",
        provider="deepseek",
        model="deepseek-v4-flash",
        cost_rank=2,
        complexity_min=0,
        complexity_max=5,
        strengths=["boilerplate", "simple_features", "tests", "crud"],
    ),
    ModelTier(
        name="deepseek-pro",
        provider="deepseek",
        model="deepseek-v4-pro",
        cost_rank=3,
        complexity_min=2,
        complexity_max=8,
        strengths=["code_generation", "debugging", "refactor", "feature"],
    ),
    ModelTier(
        name="kimi",
        provider="moonshot",
        model="kimi-k2.6",
        cost_rank=4,
        complexity_min=3,
        complexity_max=8,
        strengths=["documentation", "agentic_loops", "research"],
    ),
    ModelTier(
        name="codex",
        provider="openai",
        model="codex",
        cost_rank=5,
        complexity_min=4,
        complexity_max=10,
        strengths=["review", "bulk_generation", "api_design"],
        role="validator",
    ),
    ModelTier(
        name="claude",
        provider="anthropic",
        model="claude-sonnet-4",
        cost_rank=6,
        complexity_min=5,
        complexity_max=10,
        strengths=["complex_reasoning", "security", "architecture"],
    ),
]


@dataclass
class RoutingDecision:
    """Result of dynamic model routing."""

    primary: ModelTier
    validator: ModelTier | None = None
    reason: str = ""
    fallback_chain: list[str] = field(default_factory=list)


def route_task(
    complexity_score: int,
    task_type: str = "general",
    security_sensitive: bool = False,
    tiers: list[ModelTier] | None = None,
    stakes: str = "low",
    fatigue: float = 0.0,
) -> RoutingDecision:
    """Route a task to the optimal model tier.

    Args:
        complexity_score: 0-10 from polyphony scoring
        task_type: "bug", "feature", "refactor", "test", etc.
        security_sensitive: True for auth/billing/PII tasks
        tiers: Custom tiers (defaults to DEFAULT_TIERS)
    """
    available = tiers or DEFAULT_TIERS
    primaries = [
        t for t in available if t.role == "primary"
    ]
    validators = [
        t for t in available if t.role == "validator"
    ]

    primary = _select_primary(
        complexity_score, task_type, primaries, stakes, fatigue,
    )
    validator = _select_validator(
        complexity_score, security_sensitive, validators, stakes,
    )
    fallback = _build_fallback(primary, primaries)
    reason = _build_reason(
        primary, complexity_score, task_type, security_sensitive
    )

    return RoutingDecision(
        primary=primary,
        validator=validator,
        reason=reason,
        fallback_chain=fallback,
    )


def _select_primary(
    score: int,
    task_type: str,
    tiers: list[ModelTier],
    stakes: str = "low",
    fatigue: float = 0.0,
) -> ModelTier:
    """Pick the cheapest tier that handles the complexity."""
    candidates = [
        t for t in tiers
        if t.complexity_min <= score <= t.complexity_max
    ]
    if not candidates:
        return tiers[-1]  # Fallback to most capable

    candidates.sort(key=lambda t: t.cost_rank)

    # High stakes or security: skip cheapest tiers
    high_risk = (
        stakes == "high"
        or task_type in ("security", "auth", "billing")
    )
    if high_risk:
        capable = [
            c for c in candidates if c.cost_rank >= 3
        ]
        if capable:
            return capable[0]

    # Fatigue escalation: use capable models when tired
    if fatigue >= _REM:
        premium = _tier_at_rank(candidates, tiers, 4)
        if premium:
            return premium
    if fatigue >= _ESCALATE:
        mid = _tier_at_rank(candidates, tiers, 3)
        if mid:
            return mid

    return candidates[0]


def _select_validator(
    score: int,
    security_sensitive: bool,
    validators: list[ModelTier],
    stakes: str = "low",
) -> ModelTier | None:
    """Add validation for high-risk tasks."""
    if not validators:
        return None
    if score >= 8 or security_sensitive or stakes == "high":
        return validators[0]
    return None


def _build_fallback(
    primary: ModelTier,
    tiers: list[ModelTier],
) -> list[str]:
    """Build fallback chain: next tier up, then next."""
    above = [
        t for t in tiers
        if t.cost_rank > primary.cost_rank
    ]
    above.sort(key=lambda t: t.cost_rank)
    return [t.name for t in above]


def _tier_at_rank(
    candidates: list[ModelTier],
    all_tiers: list[ModelTier],
    min_rank: int,
) -> ModelTier | None:
    """Find cheapest tier at or above min_rank."""
    pool = [c for c in candidates if c.cost_rank >= min_rank]
    if not pool:
        pool = [t for t in all_tiers if t.cost_rank >= min_rank]
    pool.sort(key=lambda t: t.cost_rank)
    return pool[0] if pool else None


def _build_reason(
    primary: ModelTier,
    score: int,
    task_type: str,
    security_sensitive: bool,
) -> str:
    """Human-readable routing explanation."""
    parts = [f"complexity={score}/10"]
    if task_type != "general":
        parts.append(f"type={task_type}")
    if security_sensitive:
        parts.append("security-sensitive")
    parts.append(f"routed to {primary.name}")
    return ", ".join(parts)
