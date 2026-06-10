"""Plane 2 — Validation: F2 from Cortex drift_events.

F2 = 1 - (sum of per-reason capped severity / active reasons).
Per-reason severity is capped at 1.0 to prevent one noisy
reason from dominating the score.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def compute_f2(
    drift: list[dict[str, Any]],
    reasons: list[dict[str, Any]],
) -> float:
    reason_count = max(len(reasons), 1)
    if not drift:
        return 1.0
    by_reason: dict[str, float] = defaultdict(float)
    for d in drift:
        rid = d["from_reason_id"]
        by_reason[rid] += d["severity"]
    total = sum(min(s, 1.0) for s in by_reason.values())
    f2 = 1.0 - total / reason_count
    return max(f2, 0.0)
