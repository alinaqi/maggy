"""Dynamic model routing — routes tasks to models by complexity.

Not just fallback chains: intelligent routing based on task complexity,
security sensitivity, and task type. Simple tasks go to cheap models,
complex tasks to premium, security-critical get dual validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import ModelTier


DEFAULT_TIERS: list[ModelTier] = [
    ModelTier(
        name="local",
        provider="ollama",
        model="qwen3-coder:30b-a3b-q8_0",
        cost_rank=1,
        complexity_min=0,
        complexity_max=5,
        strengths=["formatting", "simple_edits", "crud", "feature"],
    ),
    ModelTier(
        name="kimi",
        provider="moonshot",
        model="kimi-k2",
        cost_rank=2,
        complexity_min=0,
        complexity_max=5,
        strengths=["documentation", "simple_tasks"],
    ),
    ModelTier(
        name="codex",
        provider="openai",
        model="codex",
        cost_rank=3,
        complexity_min=4,
        complexity_max=10,
        strengths=["code_generation", "api_design", "review"],
    ),
    ModelTier(
        name="claude",
        provider="anthropic",
        model="claude-sonnet-4",
        cost_rank=4,
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
        complexity_score, task_type, primaries, stakes,
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
