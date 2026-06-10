"""Routing rules YAML I/O — load, save, serialize, deserialize."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from maggy.config import CONFIG_DIR

if TYPE_CHECKING:
    from maggy.routing_rules import (
        CascadePolicy,
        ModelOverride,
        PerformanceRecord,
        RoutingRules,
        StakesLevel,
        StakesPatterns,
    )

RULES_PATH = CONFIG_DIR / "routing-rules.yaml"


def save(rules: RoutingRules, path: Path | None = None) -> None:
    """Write rules to YAML."""
    target = path or RULES_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    data = to_dict(rules)
    target.write_text(yaml.safe_dump(data, sort_keys=False))


def load(path: Path | None = None) -> RoutingRules:
    """Load rules from YAML. Seeds defaults if missing."""
    from maggy.routing_rules_defaults import default_conventions, default_rules

    target = path or RULES_PATH
    if not target.exists():
        rules = default_rules()
        save(rules, target)
        return rules
    rules = from_yaml(target)
    if not rules.conventions:
        rules.conventions = default_conventions()
        save(rules, target)
    return rules


def to_dict(rules: RoutingRules) -> dict:
    """Serialize RoutingRules to a plain dict for YAML."""
    return {
        "version": rules.version,
        "updated_at": rules.updated_at,
        "stakes_patterns": _stakes_to_dict(rules.stakes),
        "cascade_policy": _cascade_to_dict(rules.cascade),
        "conventions": [
            {"text": c.text, "applies_to": c.applies_to, "source": c.source}
            for c in rules.conventions
        ],
        "project_conventions": {
            k: [{"text": c.text, "applies_to": c.applies_to, "source": c.source} for c in v]
            for k, v in rules.project_conventions.items()
        },
        "task_type_overrides": {
            k: _override_to_dict(v)
            for k, v in rules.task_type_overrides.items()
        },
        "pipeline_phases": {
            k: _override_to_dict(v)
            for k, v in rules.pipeline_phases.items()
        },
        "model_performance": {
            k: _perf_to_dict(v)
            for k, v in rules.model_performance.items()
        },
    }


def from_yaml(path: Path) -> RoutingRules:
    """Deserialize RoutingRules from a YAML file."""
    from maggy.routing_rules import (
        CascadePolicy as CP,
        Convention,
        ModelOverride as MO,
        PerformanceRecord as PR,
        RoutingRules as RR,
    )

    data = yaml.safe_load(path.read_text()) or {}
    overrides = {
        k: MO(**v)
        for k, v in (data.get("task_type_overrides") or {}).items()
    }
    phases = {
        k: MO(**v)
        for k, v in (data.get("pipeline_phases") or {}).items()
    }
    perf = {
        k: PR(**v)
        for k, v in (data.get("model_performance") or {}).items()
    }
    convs = [
        Convention(**c) for c in (data.get("conventions") or [])
    ]
    proj_convs: dict[str, list] = {}
    for pk, cv_list in (data.get("project_conventions") or {}).items():
        proj_convs[pk] = [Convention(**c) for c in cv_list]
    stakes = _stakes_from_dict(data.get("stakes_patterns") or {})
    cascade_raw = data.get("cascade_policy") or {}
    cascade = CP(**cascade_raw) if cascade_raw else CP()
    return RR(
        version=data.get("version", 1),
        updated_at=data.get("updated_at", ""),
        task_type_overrides=overrides,
        pipeline_phases=phases,
        model_performance=perf,
        conventions=convs,
        project_conventions=proj_convs,
        stakes=stakes,
        cascade=cascade,
    )


def _stakes_to_dict(stakes: StakesPatterns) -> dict:
    return {
        "high": _level_to_dict(stakes.high),
        "medium": _level_to_dict(stakes.medium),
        "low": _level_to_dict(stakes.low),
    }


def _level_to_dict(level: StakesLevel) -> dict:
    return {
        "file_patterns": level.file_patterns,
        "task_types": level.task_types,
        "keywords": level.keywords,
    }


def _cascade_to_dict(cascade: CascadePolicy) -> dict:
    return {
        "enabled": cascade.enabled,
        "min_blast": cascade.min_blast,
        "min_stakes": cascade.min_stakes,
        "max_attempts": cascade.max_attempts,
        "quality_threshold": cascade.quality_threshold,
    }


def _override_to_dict(v: ModelOverride) -> dict:
    return {
        "model": v.model, "reason": v.reason,
        "confidence": v.confidence, "source": v.source,
        "status": v.status,
    }


def _perf_to_dict(v: PerformanceRecord) -> dict:
    return {
        "strengths": v.strengths, "weaknesses": v.weaknesses,
        "tasks_completed": v.tasks_completed,
        "success_rate": v.success_rate,
    }


def _stakes_from_dict(raw: dict) -> StakesPatterns:
    from maggy.routing_rules import StakesLevel as SL
    from maggy.routing_rules import StakesPatterns as SP

    def _level(d: dict) -> SL:
        return SL(
            file_patterns=d.get("file_patterns", []),
            task_types=d.get("task_types", []),
            keywords=d.get("keywords", []),
        )

    if not raw:
        from maggy.routing_rules_defaults import default_stakes
        return default_stakes()
    return SP(
        high=_level(raw.get("high", {})),
        medium=_level(raw.get("medium", {})),
        low=_level(raw.get("low", {})),
    )
