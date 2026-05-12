"""Stakes classification — HIGH/MEDIUM/LOW from task metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maggy.providers.base import Task
    from maggy.routing_rules import StakesLevel, StakesPatterns


@dataclass
class StakesResult:
    """Result of stakes classification."""

    level: str  # "high" | "medium" | "low"
    reasons: list[str] = field(default_factory=list)


def classify_stakes(
    task: Task,
    patterns: StakesPatterns | None = None,
) -> StakesResult:
    """Classify task stakes from metadata and text."""
    if patterns is None:
        from maggy.routing_rules_defaults import default_stakes
        patterns = default_stakes()

    text = f"{task.title} {task.description}".lower()
    raw = task.raw if isinstance(task.raw, dict) else {}
    task_type = str(raw.get("task_type", ""))

    reasons: list[str] = []
    if _matches(text, task_type, patterns.high, reasons):
        return StakesResult("high", reasons)
    if _matches(text, task_type, patterns.medium, reasons):
        return StakesResult("medium", reasons)
    return StakesResult("low", ["default"])


def _matches(
    text: str, task_type: str,
    level: "StakesLevel", reasons: list[str],
) -> bool:
    """Check if text/task_type matches a stakes level."""
    matched = False
    for pat in level.file_patterns:
        if re.search(re.escape(pat), text):
            reasons.append(f"file:{pat}")
            matched = True
    if task_type and task_type in level.task_types:
        reasons.append(f"type:{task_type}")
        matched = True
    for kw in level.keywords:
        if kw.lower() in text:
            reasons.append(f"keyword:{kw}")
            matched = True
    return matched
