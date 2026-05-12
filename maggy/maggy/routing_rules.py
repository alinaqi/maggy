"""Routing rules — task-type, pipeline-phase, stakes, cascade config.

Loaded from ~/.maggy/routing-rules.yaml. Maggy can self-update
this file when benchmark or outcome data provides evidence for
better routing decisions. Manual edits are preserved.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

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
class StakesLevel:
    """Patterns for a single stakes level."""

    file_patterns: list[str] = field(default_factory=list)
    task_types: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass
class StakesPatterns:
    """Stakes classification config — high/medium/low."""

    high: StakesLevel = field(default_factory=StakesLevel)
    medium: StakesLevel = field(default_factory=StakesLevel)
    low: StakesLevel = field(default_factory=StakesLevel)


@dataclass
class CascadePolicy:
    """Cascade execution policy."""

    enabled: bool = True
    min_blast: int = 5
    min_stakes: str = "medium"
    max_attempts: int = 3
    quality_threshold: int = 3


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
    conventions: list[Convention] = field(default_factory=list)
    project_conventions: dict[str, list[Convention]] = field(
        default_factory=dict,
    )
    stakes: StakesPatterns = field(default_factory=StakesPatterns)
    cascade: CascadePolicy = field(default_factory=CascadePolicy)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_override(
    rules: RoutingRules, task_type: str,
    phase: str | None = None,
) -> str | None:
    """Return model name if rules override routing."""
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
    rules: RoutingRules, model: str,
    task_type: str, success: bool,
    path: Path | None = None,
) -> None:
    """Update performance data from a task outcome."""
    from maggy.routing_rules_io import save

    perf = rules.model_performance.get(model)
    if perf is None:
        perf = PerformanceRecord()
        rules.model_performance[model] = perf
    _update_perf(perf, task_type, success)
    rules.updated_at = _now_iso()
    save(rules, path)


def learn_override(
    rules: RoutingRules, task_type: str,
    model: str, reason: str,
    confidence: float = 0.7,
    path: Path | None = None,
) -> None:
    """Maggy learns a new routing override from data."""
    from maggy.routing_rules_io import save

    rules.task_type_overrides[task_type] = ModelOverride(
        model=model, reason=reason,
        confidence=confidence, source="learned",
    )
    rules.updated_at = _now_iso()
    save(rules, path)


def conventions_for(
    rules: RoutingRules, task_type: str,
    project_key: str | None = None,
) -> str:
    """Return conventions text relevant to a task type."""
    all_convs = list(rules.conventions)
    if project_key and project_key in rules.project_conventions:
        all_convs.extend(rules.project_conventions[project_key])
    lines = [
        f"- {c.text}" for c in all_convs
        if "all" in c.applies_to or task_type in c.applies_to
    ]
    if not lines:
        return ""
    return "## Team Conventions\n" + "\n".join(lines)


def _trusted(override: ModelOverride) -> bool:
    return override.confidence >= MIN_CONFIDENCE


def _update_perf(
    perf: PerformanceRecord, task_type: str, success: bool,
) -> None:
    total = perf.tasks_completed
    rate = perf.success_rate
    new_total = total + 1
    perf.tasks_completed = new_total
    perf.success_rate = round(
        (rate * total + (1.0 if success else 0.0)) / new_total, 3,
    )
    if success and task_type not in perf.strengths:
        perf.strengths.append(task_type)
    if not success and task_type not in perf.weaknesses:
        perf.weaknesses.append(task_type)
