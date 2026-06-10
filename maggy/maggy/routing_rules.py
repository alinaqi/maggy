"""Routing rules — task-type, pipeline-phase, stakes, cascade config.

Loaded from ~/.maggy/routing-rules.yaml. Maggy can self-update
this file when benchmark or outcome data provides evidence for
better routing decisions. Manual edits are preserved.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MIN_CONFIDENCE = 0.6
# A learned override must be backed by at least this many outcomes for the
# model+task_type, at or above MIN_SUCCESS_RATE, before it can be promoted
# from shadow to active. Guards the self-tuning feedback loop.
MIN_SAMPLES = 5
MIN_SUCCESS_RATE = 0.6


@dataclass
class ModelOverride:
    """Force a specific model for a task type or phase."""

    model: str
    reason: str = ""
    confidence: float = 1.0
    source: str = "rule"
    # active = applied; shadow = learned but NOT applied until promoted via
    # outcome-validity + approval. Manual/default rules default to active.
    status: str = "active"


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
        if override.model != "auto" and _applies(override):
            return override.model
    if task_type in rules.task_type_overrides:
        override = rules.task_type_overrides[task_type]
        if _applies(override):
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
) -> ModelOverride:
    """Propose a learned override in SHADOW mode — NOT applied.

    The proposal is recorded but never affects routing until `promote_override`
    accepts it (outcome-validity + approval). This breaks the unguarded
    self-tuning feedback loop. Returns the shadow override.
    """
    from maggy.routing_rules_io import save

    override = ModelOverride(
        model=model, reason=reason,
        confidence=confidence, source="learned", status="shadow",
    )
    rules.task_type_overrides[task_type] = override
    rules.updated_at = _now_iso()
    _audit("propose", task_type, model, reason, path)
    save(rules, path)
    return override


def promote_override(
    rules: RoutingRules, task_type: str,
    min_samples: int = MIN_SAMPLES,
    min_success: float = MIN_SUCCESS_RATE,
    path: Path | None = None,
) -> bool:
    """Promote a shadow override to active — gated on outcome-validity.

    Intended to be called by the inbox approval flow. Refuses unless the
    model has enough valid outcomes for the task type (min_samples at or
    above min_success), so a bad week or gamed metric can't become policy.
    Returns True if promoted.
    """
    from maggy.routing_rules_io import save

    override = rules.task_type_overrides.get(task_type)
    if not override or override.status != "shadow":
        return False
    perf = rules.model_performance.get(override.model)
    if perf is None or perf.tasks_completed < min_samples:
        return False
    if perf.success_rate < min_success or task_type not in perf.strengths:
        return False
    override.status = "active"
    rules.updated_at = _now_iso()
    _audit("promote", task_type, override.model, override.reason, path)
    save(rules, path)
    return True


def revert_override(
    rules: RoutingRules, task_type: str, path: Path | None = None,
) -> bool:
    """Remove an override (audit-logged, revertible)."""
    from maggy.routing_rules_io import save

    override = rules.task_type_overrides.pop(task_type, None)
    if override is None:
        return False
    rules.updated_at = _now_iso()
    _audit("revert", task_type, override.model, override.reason, path)
    save(rules, path)
    return True


def pending_overrides(rules: RoutingRules) -> dict[str, ModelOverride]:
    """Shadow overrides awaiting promotion (for the inbox/approval UI)."""
    return {
        tt: ov for tt, ov in rules.task_type_overrides.items()
        if ov.status == "shadow"
    }


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


def _applies(override: ModelOverride) -> bool:
    """A rule only routes traffic if it's active AND trusted."""
    return override.status == "active" and _trusted(override)


def _audit_path(path: Path | None) -> Path:
    base = path or (Path.home() / ".maggy" / "routing-rules.yaml")
    return base.parent / "routing-rules-audit.jsonl"


def _audit(
    action: str, task_type: str, model: str, reason: str,
    path: Path | None = None,
) -> None:
    """Append a revertible audit record for every rule change."""
    rec = {
        "ts": _now_iso(), "action": action, "task_type": task_type,
        "model": model, "reason": reason,
    }
    try:
        ap = _audit_path(path)
        ap.parent.mkdir(parents=True, exist_ok=True)
        with ap.open("a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass


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
