"""Dynamic model routing — routes tasks to models by complexity.

Not just fallback chains: intelligent routing based on task complexity,
security sensitivity, and task type. Simple tasks go to cheap models,
complex tasks to premium, security-critical get dual validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import json
from datetime import datetime, timezone
from pathlib import Path

from maggy.mnemos.constants import (
    FATIGUE_ROUTING_ESCALATE as _ESCALATE,
    FATIGUE_ROUTING_PREMIUM as _REM,
)

from .models import ModelTier
from maggy.provider_config import ProviderConfig, load_provider_config

# Model-level budget caps (daily, in USD) — block/demote when exceeded
MODEL_DAILY_BUDGETS: dict[str, float] = {
    "claude": 2.00,         # Max $2/day for Claude — back off after 50% of this
    "gemini-pro-search": 1.00,
    "codex": 1.50,
    "kimi": 0.50,
}
# Warning threshold: start biasing away at this fraction of budget
BUDGET_WARN_THRESHOLD = 0.5   # 50% of daily budget → start demoting
BUDGET_BLOCK_THRESHOLD = 0.8  # 80% → block entirely for non-critical tasks


def _flash_tier(cfg: ProviderConfig) -> ModelTier:
    """Build the flash tier from provider config."""
    provider = cfg.flash_provider()
    model = cfg.flash_model()
    return ModelTier(
        name=f"{provider}-flash",
        provider=provider,
        model=model,
        cost_rank=3,
        complexity_min=0,
        complexity_max=5,
        strengths=["boilerplate", "simple_features", "tests", "crud"],
    )


def _pro_tier(cfg: ProviderConfig) -> ModelTier:
    """Build the pro tier from provider config."""
    provider = cfg.pro_provider()
    model = cfg.pro_model()
    return ModelTier(
        name=f"{provider}-pro",
        provider=provider,
        model=model,
        cost_rank=4,
        complexity_min=2,
        complexity_max=8,
        strengths=["code_generation", "debugging", "refactor", "feature"],
    )


def build_tiers(cfg: ProviderConfig | None = None) -> list[ModelTier]:
    """Build the full tier list, substituting flash/pro from provider config."""
    resolved = cfg or load_provider_config()
    return [
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
            name="gemini-flash-lite",
            provider="google",
            model="gemini-2.5-flash-lite",
            cost_rank=2,
            complexity_min=0,
            complexity_max=4,
            strengths=["bulk_extraction", "classification", "cheap_summarization"],
        ),
        _flash_tier(resolved),
        _pro_tier(resolved),
    ]


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
        name="gemini-flash-lite",
        provider="google",
        model="gemini-2.5-flash-lite",
        cost_rank=2,
        complexity_min=0,
        complexity_max=4,
        strengths=["bulk_extraction", "classification", "cheap_summarization"],
    ),
    ModelTier(
        name="groq-flash",
        provider="groq",
        model="llama-3.3-70b-versatile",
        cost_rank=3,
        complexity_min=0,
        complexity_max=5,
        strengths=["boilerplate", "simple_features", "tests", "crud"],
    ),
    ModelTier(
        name="together-pro",
        provider="together",
        model="meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
        cost_rank=4,
        complexity_min=2,
        complexity_max=8,
        strengths=["code_generation", "debugging", "refactor", "feature"],
    ),
    ModelTier(
        name="gemini-flash",
        provider="google",
        model="gemini-2.5-flash",
        cost_rank=5,
        complexity_min=1,
        complexity_max=6,
        strengths=["multimodal", "video_analysis", "image_analysis", "brand_assets"],
    ),
    ModelTier(
        name="kimi",
        provider="moonshot",
        model="kimi-k2.6",
        cost_rank=6,
        complexity_min=3,
        complexity_max=8,
        strengths=["documentation", "agentic_loops", "research"],
    ),
    ModelTier(
        name="grok",
        provider="xai",
        model="grok-4.3",
        cost_rank=7,
        complexity_min=4,
        complexity_max=10,
        strengths=["competitor_intel", "ckg_building", "deep_reasoning",
                   "truthful_insights", "market_analysis"],
    ),
    ModelTier(
        name="gemini-pro-search",
        provider="google",
        model="gemini-3.1-pro",
        cost_rank=8,
        complexity_min=5,
        complexity_max=10,
        strengths=["deep_research", "google_grounding", "competitor_intel",
                   "market_research", "large_context"],
    ),
    ModelTier(
        name="codex",
        provider="openai",
        model="codex",
        cost_rank=9,
        complexity_min=4,
        complexity_max=10,
        strengths=["review", "bulk_generation", "api_design"],
        role="validator",
    ),
    ModelTier(
        name="claude",
        provider="anthropic",
        model="claude-sonnet-4",
        cost_rank=10,
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
    available = tiers or build_tiers()
    primaries = [
        t for t in available if t.role == "primary"
    ]
    validators = [
        t for t in available if t.role == "validator"
    ]

    model_usage = _get_model_usage_today()
    primary = _select_primary(
        complexity_score, task_type, primaries, stakes, fatigue,
        model_usage=model_usage,
    )
    validator = _select_validator(
        complexity_score, security_sensitive, validators, stakes,
    )
    fallback = _build_fallback(primary, primaries)
    reason = _build_reason(
        primary, complexity_score, task_type, security_sensitive,
        model_usage=model_usage,
    )

    return RoutingDecision(
        primary=primary,
        validator=validator,
        reason=reason,
        fallback_chain=fallback,
    )


def _get_model_usage_today() -> dict[str, float]:
    """Read routing log and estimate per-model spend for today."""
    path = Path.home() / ".claude" / "routing-log.jsonl"
    if not path.exists():
        return {}

    now = datetime.now(timezone.utc)
    since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    usage: dict[str, float] = {}

    # Cost per token estimates for spend calculation
    rates = {
        "claude": 3.0, "codex": 2.5, "gemini-pro-search": 1.25,
        "kimi": 0.6, "deepseek-pro": 0.44, "gemini-flash": 0.15,
        "deepseek-flash": 0.14, "gemini-flash-lite": 0.10,
    }

    for line in path.read_text().strip().split("\n"):
        try:
            entry = json.loads(line)
            ts = entry.get("ts", "")
            ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts_dt < since:
                continue
            tier = entry.get("tier", "").lower().replace("_", "-")
            saved = entry.get("tokens_saved", 0) or 0
            est_tokens = saved * 2  # rough estimate
            rate = rates.get(tier, 0.44)
            usage[tier] = usage.get(tier, 0.0) + (est_tokens / 1_000_000) * rate
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    return usage


def _select_primary(
    score: int,
    task_type: str,
    tiers: list[ModelTier],
    stakes: str = "low",
    fatigue: float = 0.0,
    model_usage: dict[str, float] | None = None,
) -> ModelTier:
    """Pick the cheapest tier that handles the complexity, factoring in agent fatigue AND model-level budget/usage fatigue."""
    candidates = [
        t for t in tiers
        if t.complexity_min <= score <= t.complexity_max
    ]
    if not candidates:
        return tiers[-1]

    candidates.sort(key=lambda t: t.cost_rank)

    # Model budget check: if a model is overused today, demote or block it
    if model_usage is None:
        model_usage = _get_model_usage_today()

    # Filter out models that have exceeded their daily budget
    budget_filtered = []
    for c in candidates:
        daily_budget = MODEL_DAILY_BUDGETS.get(c.name, 999.0)
        spent_today = model_usage.get(c.name, 0.0)
        usage_pct = spent_today / daily_budget if daily_budget > 0 else 0.0

        # Block: >80% budget used, and this isn't critical
        if usage_pct >= BUDGET_BLOCK_THRESHOLD and task_type not in ("security", "auth", "billing") and stakes != "high":
            continue  # Skip this model entirely

        # Warn: >50% budget — only include if this is the cheapest OR the task is high-complexity
        if usage_pct >= BUDGET_WARN_THRESHOLD and c.cost_rank > candidates[0].cost_rank and score < 7:
            continue  # Skip — there's a cheaper model available

        budget_filtered.append(c)

    if budget_filtered:
        candidates = budget_filtered

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

    # Agent fatigue escalation: use capable models when tired
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
    model_usage: dict[str, float] | None = None,
) -> str:
    """Human-readable routing explanation, including budget/fatigue info."""
    parts = [f"complexity={score}/10"]
    if task_type != "general":
        parts.append(f"type={task_type}")
    if security_sensitive:
        parts.append("security-sensitive")

    # Add model budget status
    if model_usage:
        spent = model_usage.get(primary.name, 0.0)
        budget = MODEL_DAILY_BUDGETS.get(primary.name)
        if budget and spent > 0:
            pct = spent / budget * 100
            if pct > 80:
                parts.append(f"budget={pct:.0f}% (near cap, would demote if non-critical)")
            elif pct > 50:
                parts.append(f"budget={pct:.0f}%")

    parts.append(f"routed to {primary.name}")
    return ", ".join(parts)
