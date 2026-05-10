"""Report generator — produces the 5-minute process analysis.

Answers:
1. Why are your PRs slow?
2. What do reviewers always flag?
3. Which model should handle which task?
4. What will Maggy change before the next PR?
"""

from __future__ import annotations

from .models import (
    CISignal,
    ProcessReport,
    ReviewSignal,
    VelocitySignal,
)


def generate_summary(report: ProcessReport) -> str:
    """Build human-readable summary from report data."""
    lines: list[str] = []

    lines.append(
        f"## Process Report: {report.project_key}"
    )
    lines.append(
        f"Analyzed {report.total_prs} PRs"
    )
    lines.append("")

    # Velocity
    if report.velocity:
        v = report.velocity
        lines.append("### PR Velocity")
        lines.append(
            f"- Avg time to merge: {v.avg_time_to_merge_hours:.1f}h"
        )
        lines.append(
            f"- Median time to merge: "
            f"{v.median_time_to_merge_hours:.1f}h"
        )
        lines.append(
            f"- Avg review rounds: {v.avg_review_rounds:.1f}"
        )
        lines.append(
            f"- Avg PR size: {v.avg_pr_size:.0f} lines"
        )
        lines.append("")

    # Review patterns
    if report.review_signals:
        lines.append("### Recurring Review Themes")
        for sig in report.review_signals[:5]:
            lines.append(
                f"- **{sig.reviewer}** flags "
                f"*{sig.theme.replace('_', ' ')}* "
                f"({sig.count}x)"
            )
        lines.append("")

    # CI failures
    if report.ci_signals:
        lines.append("### CI Failure Patterns")
        for sig in report.ci_signals[:5]:
            lines.append(
                f"- **{sig.check_name}**: fails "
                f"{sig.failure_rate:.0%} of runs"
            )
            if sig.correlated_files:
                files = ", ".join(sig.correlated_files[:3])
                lines.append(f"  Correlated with: {files}")
        lines.append("")

    # Routing
    if report.routing_recommendations:
        lines.append("### Model Routing Recommendations")
        for rec in report.routing_recommendations:
            model = rec.get("model", "?")
            pattern = rec.get("pattern", "?")
            lines.append(f"- {pattern} -> **{model}**")
            val = rec.get("validation")
            if val:
                lines.append(
                    f"  + validation by **{val}**"
                )
        lines.append("")

    # Fixes
    if report.preemptive_fixes:
        lines.append("### Pre-emptive Fixes")
        for fix in report.preemptive_fixes:
            lines.append(f"- {fix}")
        lines.append("")

    return "\n".join(lines)


def format_health_metrics(
    velocity: VelocitySignal | None,
    ci_signals: list[CISignal],
    review_signals: list[ReviewSignal],
) -> dict:
    """Format as structured health dashboard data."""
    health: dict = {"status": "unknown"}

    if velocity:
        health["velocity"] = {
            "avg_merge_hours": (
                velocity.avg_time_to_merge_hours
            ),
            "median_merge_hours": (
                velocity.median_time_to_merge_hours
            ),
            "avg_review_rounds": velocity.avg_review_rounds,
            "avg_pr_size": velocity.avg_pr_size,
            "prs_analyzed": velocity.total_prs_analyzed,
        }

    ci_pass_rate = _ci_pass_rate(ci_signals)
    health["ci_pass_rate"] = ci_pass_rate
    health["top_review_themes"] = [
        {"reviewer": s.reviewer, "theme": s.theme, "count": s.count}
        for s in review_signals[:5]
    ]

    # Overall status
    if velocity and ci_pass_rate is not None:
        if (
            velocity.avg_review_rounds <= 1.5
            and ci_pass_rate >= 0.9
        ):
            health["status"] = "healthy"
        elif (
            velocity.avg_review_rounds <= 2.5
            and ci_pass_rate >= 0.7
        ):
            health["status"] = "moderate"
        else:
            health["status"] = "needs_attention"

    return health


def _ci_pass_rate(
    ci_signals: list[CISignal],
) -> float | None:
    """Overall CI pass rate across all checks."""
    total_runs = sum(s.total_runs for s in ci_signals)
    total_fails = sum(s.failure_count for s in ci_signals)
    if total_runs == 0:
        return None
    return 1.0 - (total_fails / total_runs)
