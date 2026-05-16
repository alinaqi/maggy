"""Default routing rules — seed data for first-run initialization."""

from __future__ import annotations

from maggy.routing_rules import (
    CascadePolicy,
    Convention,
    ModelOverride,
    PerformanceRecord,
    RoutingRules,
    StakesLevel,
    StakesPatterns,
    _now_iso,
)

_CONV_DATA = [
    ("mWP: Ship minimum wowable product, not MVP. "
     "Target 5-7 on the 11-star scale.", ["all"]),
    ("TDD: RED (failing tests) -> GREEN (minimal code) "
     "-> VALIDATE (lint, types, coverage >= 80%).",
     ["feature", "bug", "refactor"]),
    ("No secrets in code. Parameterized SQL only. "
     "Validate at API boundaries.", ["all"]),
    ("Quality gates: max 20 lines/function, 3 params, "
     "2 nesting levels, 200 lines/file.", ["all"]),
    ("Use existing patterns. Read codebase before "
     "changing. Keep changes minimal.", ["all"]),
]

_OVERRIDES = {
    "docs": ("deepseek-pro", "Prose-capable, cost-efficient", 0.9, "benchmark"),
    "security": ("claude", "Deep reasoning needed", 1.0, "rule"),
    "architecture": ("claude", "Cross-context awareness", 0.8, "rule"),
    "tests": ("deepseek-pro", "Strong test generation", 0.9, "benchmark"),
    "planning": ("claude", "Structured reasoning", 0.8, "rule"),
}

_PHASES = {
    "spec": ("claude", "Comprehensive docs", 1.0, "rule"),
    "tdd_red": ("deepseek-pro", "Test design", 0.9, "rule"),
    "tdd_green": ("auto", "Blast-score routing", 1.0, "rule"),
    "review": ("claude", "Security+arch depth", 1.0, "rule"),
}

_PERF = {
    "claude": (["security", "architecture", "planning"], ["cost"], 9, 1.0),
    "gemini-pro-search": (["deep_research", "google_grounding", "competitor_intel", "market_research", "large_context"], ["code_generation"], 7, 1.0),
    "deepseek-pro": (["code_generation", "debugging", "refactor", "tests", "docs"], ["security"], 5, 1.0),
    "deepseek-flash": (["boilerplate", "simple_features", "crud", "tests"], ["complex_reasoning"], 3, 1.0),
    "gemini-flash": (["multimodal", "video_analysis", "image_analysis", "brand_assets"], ["code_generation", "complex_reasoning"], 4, 1.0),
    "gemini-flash-lite": (["bulk_extraction", "classification", "cheap_summarization"], ["code_generation", "complex_reasoning"], 2, 1.0),
    "codex": (["review", "bulk_generation", "api_design"], ["docs"], 5, 1.0),
    "kimi": (["documentation", "agentic_loops", "research"], ["complex_reasoning"], 1, 1.0),
    "local": (["code_formatting", "simple_edits"], ["docs", "prose"], 1, 1.0),
}


def default_conventions() -> list[Convention]:
    """Team conventions from claude-bootstrap skills."""
    return [Convention(t, a, "claude-bootstrap") for t, a in _CONV_DATA]


def default_stakes() -> StakesPatterns:
    return StakesPatterns(
        high=StakesLevel(
            ["auth", "billing", "payment", "migration",
             "security", "deploy", "infra", ".env"],
            ["security", "auth", "billing", "migration"],
            ["production", "customer data", "breaking change"],
        ),
        medium=StakesLevel(
            ["api", "routes", "models", "schema", "database"],
            ["feature", "refactor"],
        ),
        low=StakesLevel([], ["docs", "formatting", "tests"]),
    )


def default_rules() -> RoutingRules:
    """Seed rules from benchmark evidence + team conventions."""
    return RoutingRules(
        version=1, updated_at=_now_iso(),
        conventions=default_conventions(),
        stakes=default_stakes(),
        cascade=CascadePolicy(),
        task_type_overrides={
            k: ModelOverride(*v) for k, v in _OVERRIDES.items()
        },
        pipeline_phases={
            k: ModelOverride(*v) for k, v in _PHASES.items()
        },
        model_performance={
            k: PerformanceRecord(*v) for k, v in _PERF.items()
        },
    )
