"""Routing rules — task-type and pipeline-phase model assignments.

Loaded from ~/.maggy/routing-rules.yaml. Maggy can self-update
this file when benchmark or outcome data provides evidence for
better routing decisions. Manual edits are preserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from maggy.config import CONFIG_DIR

RULES_PATH = CONFIG_DIR / "routing-rules.yaml"
MIN_CONFIDENCE = 0.6


@dataclass
class ModelOverride:
    """Force a specific model for a task type or phase."""

    model: str
    reason: str = ""
    confidence: float = 1.0
    source: str = "rule"


@dataclass
class PerformanceRecord:
    """Tracked model performance from outcomes."""

    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    tasks_completed: int = 0
    success_rate: float = 0.0


@dataclass
class Convention:
    """A team convention injected into prompts."""

    text: str
    applies_to: list[str] = field(default_factory=list)
    source: str = "manual"


@dataclass
class RoutingRules:
    """All routing rules Maggy uses for orchestration."""

    version: int = 1
    updated_at: str = ""
    task_type_overrides: dict[str, ModelOverride] = field(
        default_factory=dict,
    )
    pipeline_phases: dict[str, ModelOverride] = field(
        default_factory=dict,
    )
    model_performance: dict[str, PerformanceRecord] = field(
        default_factory=dict,
    )
    conventions: list[Convention] = field(
        default_factory=list,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_conventions() -> list[Convention]:
    """Team conventions from claude-bootstrap skills."""
    return [
        Convention(
            "Build minimum wowable product (mWP). Ship the smallest "
            "thing that makes someone say 'wow'. No feature flags, no "
            "backwards-compat shims, no premature abstractions.",
            ["all"], "claude-bootstrap",
        ),
        Convention(
            "Follow TDD: RED (write failing tests) → GREEN (minimal "
            "code to pass) → VALIDATE (lint, types, coverage >= 80%).",
            ["feature", "bug", "refactor"], "claude-bootstrap",
        ),
        Convention(
            "No secrets in code. Parameterized SQL only. Validate all "
            "input at API boundaries. Hash passwords with bcrypt/argon2.",
            ["all"], "claude-bootstrap",
        ),
        Convention(
            "Quality gates: max 20 lines/function, max 3 params, "
            "max 2 nesting levels, max 200 lines/file.",
            ["all"], "claude-bootstrap",
        ),
        Convention(
            "Use existing patterns. Read the codebase before changing it. "
            "Keep changes minimal and focused on the task.",
            ["all"], "claude-bootstrap",
        ),
    ]


def default_rules() -> RoutingRules:
    """Seed rules from benchmark evidence + team conventions."""
    return RoutingRules(
        version=1,
        updated_at=_now_iso(),
        conventions=_default_conventions(),
        task_type_overrides={
            "docs": ModelOverride(
                "claude",
                "Local models are code-optimized, not prose",
                0.9, "benchmark",
            ),
            "security": ModelOverride(
                "claude",
                "Security review needs deep reasoning",
                1.0, "rule",
            ),
            "architecture": ModelOverride(
                "claude",
                "Architecture needs cross-context awareness",
                0.8, "rule",
            ),
            "tests": ModelOverride(
                "claude",
                "Only claude generated test files in benchmark",
                0.9, "benchmark",
            ),
            "planning": ModelOverride(
                "claude",
                "Planning requires structured reasoning",
                0.8, "rule",
            ),
        },
        pipeline_phases={
            "spec": ModelOverride(
                "claude",
                "SPEC phase needs comprehensive docs",
                1.0, "rule",
            ),
            "tdd_red": ModelOverride(
                "claude",
                "RED phase needs test design expertise",
                0.9, "rule",
            ),
            "tdd_green": ModelOverride(
                "auto",
                "GREEN phase uses blast-score routing",
                1.0, "rule",
            ),
            "review": ModelOverride(
                "claude",
                "Review needs security + architecture depth",
                1.0, "rule",
            ),
        },
        model_performance={
            "claude": PerformanceRecord(
                ["security", "tests", "docs", "architecture"],
                ["cost"],
                6, 1.0,
            ),
            "codex": PerformanceRecord(
                ["crud", "api_design"],
                ["frontend_speed", "tests"],
                3, 1.0,
            ),
            "kimi": PerformanceRecord(
                ["schema", "simple_tasks"],
                ["complex_reasoning"],
                1, 1.0,
            ),
            "local": PerformanceRecord(
                ["code_formatting", "simple_edits"],
                ["docs", "prose", "planning"],
                1, 1.0,
            ),
        },
    )


def load(path: Path | None = None) -> RoutingRules:
    """Load rules from YAML. Seeds defaults if missing."""
    target = path or RULES_PATH
    if not target.exists():
        rules = default_rules()
        save(rules, target)
        return rules
    rules = _from_yaml(target)
    if not rules.conventions:
        rules.conventions = _default_conventions()
        save(rules, target)
    return rules


def save(rules: RoutingRules, path: Path | None = None) -> None:
    """Write rules to YAML."""
    target = path or RULES_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _to_dict(rules)
    target.write_text(yaml.safe_dump(data, sort_keys=False))


def apply_override(
    rules: RoutingRules,
    task_type: str,
    phase: str | None = None,
) -> str | None:
    """Return model name if rules override routing.

    Returns None if blast-score routing should be used.
    """
    if phase and phase in rules.pipeline_phases:
        override = rules.pipeline_phases[phase]
        if override.model != "auto" and _trusted(override):
            return override.model

    if task_type in rules.task_type_overrides:
        override = rules.task_type_overrides[task_type]
        if _trusted(override):
            return override.model

    return None


def record_outcome(
    rules: RoutingRules,
    model: str,
    task_type: str,
    success: bool,
    path: Path | None = None,
) -> None:
    """Update performance data from a task outcome."""
    perf = rules.model_performance.get(model)
    if perf is None:
        perf = PerformanceRecord()
        rules.model_performance[model] = perf

    total = perf.tasks_completed
    rate = perf.success_rate
    new_total = total + 1
    new_rate = (rate * total + (1.0 if success else 0.0)) / new_total
    perf.tasks_completed = new_total
    perf.success_rate = round(new_rate, 3)

    if success and task_type not in perf.strengths:
        perf.strengths.append(task_type)
    if not success and task_type not in perf.weaknesses:
        perf.weaknesses.append(task_type)

    rules.updated_at = _now_iso()
    save(rules, path)


def learn_override(
    rules: RoutingRules,
    task_type: str,
    model: str,
    reason: str,
    confidence: float = 0.7,
    path: Path | None = None,
) -> None:
    """Maggy learns a new routing override from data."""
    rules.task_type_overrides[task_type] = ModelOverride(
        model=model,
        reason=reason,
        confidence=confidence,
        source="learned",
    )
    rules.updated_at = _now_iso()
    save(rules, path)


def conventions_for(
    rules: RoutingRules, task_type: str,
) -> str:
    """Return conventions text relevant to a task type."""
    lines: list[str] = []
    for c in rules.conventions:
        if "all" in c.applies_to or task_type in c.applies_to:
            lines.append(f"- {c.text}")
    if not lines:
        return ""
    return "## Team Conventions\n" + "\n".join(lines)


def _trusted(override: ModelOverride) -> bool:
    return override.confidence >= MIN_CONFIDENCE


def _to_dict(rules: RoutingRules) -> dict:
    return {
        "version": rules.version,
        "updated_at": rules.updated_at,
        "conventions": [
            {
                "text": c.text,
                "applies_to": c.applies_to,
                "source": c.source,
            }
            for c in rules.conventions
        ],
        "task_type_overrides": {
            k: {
                "model": v.model,
                "reason": v.reason,
                "confidence": v.confidence,
                "source": v.source,
            }
            for k, v in rules.task_type_overrides.items()
        },
        "pipeline_phases": {
            k: {
                "model": v.model,
                "reason": v.reason,
                "confidence": v.confidence,
                "source": v.source,
            }
            for k, v in rules.pipeline_phases.items()
        },
        "model_performance": {
            k: {
                "strengths": v.strengths,
                "weaknesses": v.weaknesses,
                "tasks_completed": v.tasks_completed,
                "success_rate": v.success_rate,
            }
            for k, v in rules.model_performance.items()
        },
    }


def _from_yaml(path: Path) -> RoutingRules:
    data = yaml.safe_load(path.read_text()) or {}
    overrides = {
        k: ModelOverride(**v)
        for k, v in (data.get("task_type_overrides") or {}).items()
    }
    phases = {
        k: ModelOverride(**v)
        for k, v in (data.get("pipeline_phases") or {}).items()
    }
    perf = {
        k: PerformanceRecord(**v)
        for k, v in (data.get("model_performance") or {}).items()
    }
    convs = [
        Convention(**c)
        for c in (data.get("conventions") or [])
    ]
    return RoutingRules(
        version=data.get("version", 1),
        updated_at=data.get("updated_at", ""),
        task_type_overrides=overrides,
        pipeline_phases=phases,
        model_performance=perf,
        conventions=convs,
    )
