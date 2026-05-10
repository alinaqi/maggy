"""Signal extraction — derives patterns from raw PR data.

Three signal types:
- Review signals: what do reviewers always flag?
- CI signals: which checks fail and why?
- Velocity signals: how fast do PRs merge?
"""

from __future__ import annotations

import re
from collections import Counter

from .models import (
    CISignal,
    PRRecord,
    ReviewSignal,
    VelocitySignal,
)

# Keywords that indicate common review themes
REVIEW_THEMES: dict[str, list[str]] = {
    "error_handling": [
        "error", "exception", "try", "catch", "handle",
        "edge case", "null", "undefined",
    ],
    "testing": [
        "test", "coverage", "assert", "mock", "spec",
        "unit test", "missing test",
    ],
    "naming": [
        "naming", "rename", "variable name", "unclear",
        "confusing name", "readability",
    ],
    "types": [
        "type", "typing", "annotation", "any type",
        "type hint", "interface",
    ],
    "security": [
        "security", "auth", "sanitize", "inject",
        "xss", "csrf", "vulnerability",
    ],
    "performance": [
        "performance", "slow", "optimize", "n+1",
        "cache", "memory", "complexity",
    ],
    "documentation": [
        "document", "comment", "docstring", "readme",
        "jsdoc", "explain",
    ],
    "style": [
        "style", "format", "indent", "lint", "spacing",
        "consistent",
    ],
}


def extract_review_signals(
    prs: list[PRRecord],
) -> list[ReviewSignal]:
    """Find recurring reviewer complaints."""
    # reviewer -> theme -> [pr_numbers]
    hits: dict[str, dict[str, list[int]]] = {}

    for pr in prs:
        for review in pr.reviews:
            if not review.body:
                continue
            reviewer = review.reviewer
            if reviewer not in hits:
                hits[reviewer] = {}
            body_lower = review.body.lower()
            for theme, keywords in REVIEW_THEMES.items():
                if _matches_theme(body_lower, keywords):
                    theme_hits = hits[reviewer].setdefault(
                        theme, []
                    )
                    if pr.number not in theme_hits:
                        theme_hits.append(pr.number)

    signals: list[ReviewSignal] = []
    for reviewer, themes in hits.items():
        for theme, pr_nums in themes.items():
            if len(pr_nums) >= 2:
                signals.append(ReviewSignal(
                    reviewer=reviewer,
                    theme=theme,
                    count=len(pr_nums),
                    example_prs=pr_nums[:5],
                ))

    signals.sort(key=lambda s: s.count, reverse=True)
    return signals


def extract_ci_signals(
    prs: list[PRRecord],
) -> list[CISignal]:
    """Find CI failure patterns."""
    # check_name -> {failures, total, files}
    stats: dict[str, dict] = {}

    for pr in prs:
        for check in pr.checks:
            if check.name not in stats:
                stats[check.name] = {
                    "failures": 0,
                    "total": 0,
                    "files": Counter(),
                }
            stats[check.name]["total"] += 1
            if check.conclusion == "failure":
                stats[check.name]["failures"] += 1
                for f in pr.files:
                    stats[check.name]["files"][f] += 1

    signals: list[CISignal] = []
    for name, data in stats.items():
        if data["failures"] == 0:
            continue
        # Top correlated files (appear in >50% of failures)
        threshold = max(2, data["failures"] // 2)
        correlated = [
            f for f, count in data["files"].most_common(5)
            if count >= threshold
        ]
        signals.append(CISignal(
            check_name=name,
            failure_count=data["failures"],
            total_runs=data["total"],
            correlated_files=correlated,
        ))

    signals.sort(
        key=lambda s: s.failure_rate, reverse=True
    )
    return signals


def extract_velocity_signals(
    prs: list[PRRecord],
) -> VelocitySignal | None:
    """Compute PR velocity metrics."""
    merged = [p for p in prs if p.state == "merged"]
    if not merged:
        return None

    merge_times = [
        p.time_to_merge_hours
        for p in merged
        if p.time_to_merge_hours is not None
    ]
    if not merge_times:
        return None

    merge_times.sort()
    avg_time = sum(merge_times) / len(merge_times)
    median_idx = len(merge_times) // 2
    median_time = merge_times[median_idx]

    rounds = [p.review_rounds for p in merged]
    avg_rounds = sum(rounds) / len(rounds) if rounds else 0

    sizes = [p.total_lines for p in merged]
    avg_size = sum(sizes) / len(sizes) if sizes else 0

    return VelocitySignal(
        avg_time_to_merge_hours=round(avg_time, 1),
        median_time_to_merge_hours=round(median_time, 1),
        avg_review_rounds=round(avg_rounds, 2),
        avg_pr_size=round(avg_size, 1),
        total_prs_analyzed=len(merged),
    )


def _matches_theme(
    text: str, keywords: list[str]
) -> bool:
    """Check if text matches any keyword in theme."""
    return any(kw in text for kw in keywords)
