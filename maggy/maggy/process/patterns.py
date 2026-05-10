"""Pattern engine — correlates signals into actionable insights.

Takes raw signals from signals.py and produces:
- Preemptive fix recommendations
- Routing recommendations per task type
- Bottleneck identification
"""

from __future__ import annotations

from .models import (
    CISignal,
    PRRecord,
    ReviewSignal,
    VelocitySignal,
)


def identify_bottlenecks(
    velocity: VelocitySignal | None,
    prs: list[PRRecord],
) -> list[str]:
    """Identify why PRs are slow."""
    if not velocity:
        return ["Insufficient data — no merged PRs found"]

    bottlenecks: list[str] = []

    if velocity.avg_time_to_merge_hours > 48:
        bottlenecks.append(
            f"Slow merge: avg {velocity.avg_time_to_merge_hours:.0f}h "
            f"(target: <24h)"
        )

    if velocity.avg_review_rounds > 1.5:
        bottlenecks.append(
            f"High review churn: avg {velocity.avg_review_rounds:.1f} "
            f"rounds (target: <1.5)"
        )

    if velocity.avg_pr_size > 500:
        bottlenecks.append(
            f"Large PRs: avg {velocity.avg_pr_size:.0f} lines "
            f"(target: <300)"
        )

    # Size-velocity correlation
    large = [
        p for p in prs
        if p.total_lines > 500
        and p.time_to_merge_hours is not None
    ]
    small = [
        p for p in prs
        if p.total_lines <= 200
        and p.time_to_merge_hours is not None
    ]
    if large and small:
        avg_large = _avg_merge_time(large)
        avg_small = _avg_merge_time(small)
        if avg_large and avg_small and avg_large > avg_small * 2:
            ratio = avg_large / avg_small
            bottlenecks.append(
                f"Large PRs take {ratio:.1f}x longer to merge"
            )

    if not bottlenecks:
        bottlenecks.append("No major bottlenecks detected")

    return bottlenecks


def generate_preemptive_fixes(
    review_signals: list[ReviewSignal],
    ci_signals: list[CISignal],
) -> list[str]:
    """Generate actionable pre-PR fixes."""
    fixes: list[str] = []

    for sig in review_signals[:5]:
        fixes.append(
            f"Add {sig.theme.replace('_', ' ')} before PR "
            f"— reviewer {sig.reviewer} flags this "
            f"{sig.count}x"
        )

    for sig in ci_signals[:3]:
        if sig.failure_rate > 0.2:
            files = ", ".join(sig.correlated_files[:3])
            fix = (
                f"Run {sig.check_name} locally before push "
                f"— fails {sig.failure_rate:.0%} of the time"
            )
            if files:
                fix += f" (correlated with: {files})"
            fixes.append(fix)

    return fixes


def generate_routing_recs(
    prs: list[PRRecord],
) -> list[dict]:
    """Recommend model routing per task pattern."""
    recs: list[dict] = []

    # Count security-related PRs
    sec_prs = [
        p for p in prs
        if _is_security_related(p)
    ]
    if sec_prs:
        recs.append({
            "pattern": "Security/auth changes",
            "model": "claude",
            "validation": "codex",
            "reason": (
                f"{len(sec_prs)} security PRs found — "
                f"route to Claude + Codex validation"
            ),
        })

    # Count test-only PRs
    test_prs = [
        p for p in prs
        if _is_test_only(p)
    ]
    if test_prs:
        recs.append({
            "pattern": "Test-only changes",
            "model": "kimi",
            "validation": None,
            "reason": (
                f"{len(test_prs)} test-only PRs — "
                f"route to Kimi (cheaper)"
            ),
        })

    # Count doc changes
    doc_prs = [p for p in prs if _is_docs(p)]
    if doc_prs:
        recs.append({
            "pattern": "Documentation changes",
            "model": "kimi",
            "validation": None,
            "reason": (
                f"{len(doc_prs)} doc PRs — "
                f"route to Kimi"
            ),
        })

    # Complex multi-file changes
    complex_prs = [
        p for p in prs if p.changed_files >= 10
    ]
    if complex_prs:
        recs.append({
            "pattern": "Multi-file refactors (10+ files)",
            "model": "claude",
            "validation": "codex",
            "reason": (
                f"{len(complex_prs)} complex PRs — "
                f"route to Claude"
            ),
        })

    return recs


def _avg_merge_time(prs: list[PRRecord]) -> float | None:
    times = [
        p.time_to_merge_hours
        for p in prs
        if p.time_to_merge_hours is not None
    ]
    if not times:
        return None
    return sum(times) / len(times)


def _is_security_related(pr: PRRecord) -> bool:
    keywords = {"auth", "security", "token", "session"}
    title = pr.title.lower()
    return any(k in title for k in keywords) or any(
        "auth" in f or "security" in f for f in pr.files
    )


def _is_test_only(pr: PRRecord) -> bool:
    if not pr.files:
        return False
    return all(
        "test" in f.lower() or "spec" in f.lower()
        for f in pr.files
    )


def _is_docs(pr: PRRecord) -> bool:
    if not pr.files:
        return False
    return all(
        f.endswith(".md") or "doc" in f.lower()
        for f in pr.files
    )
