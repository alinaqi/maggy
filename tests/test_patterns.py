"""Tests for pattern correlation engine."""

import pytest

from maggy.process.models import (
    CISignal,
    PRRecord,
    ReviewSignal,
    VelocitySignal,
)
from maggy.process.patterns import (
    generate_preemptive_fixes,
    generate_routing_recs,
    identify_bottlenecks,
)


def _pr(
    number: int = 1,
    title: str = "Fix bug",
    additions: int = 50,
    deletions: int = 10,
    changed_files: int = 3,
    files: list | None = None,
    state: str = "merged",
    created_at: str = "2026-01-01T00:00:00Z",
    merged_at: str | None = "2026-01-02T00:00:00Z",
) -> PRRecord:
    return PRRecord(
        number=number,
        title=title,
        author="dev",
        state=state,
        created_at=created_at,
        merged_at=merged_at,
        additions=additions,
        deletions=deletions,
        changed_files=changed_files,
        head_sha="abc",
        base_branch="main",
        files=files or [],
    )


class TestBottlenecks:
    def test_slow_merge(self):
        velocity = VelocitySignal(
            avg_time_to_merge_hours=72.0,
            median_time_to_merge_hours=60.0,
            avg_review_rounds=1.0,
            avg_pr_size=200,
            total_prs_analyzed=10,
        )
        result = identify_bottlenecks(velocity, [])
        assert any("Slow merge" in b for b in result)

    def test_high_review_rounds(self):
        velocity = VelocitySignal(
            avg_time_to_merge_hours=12.0,
            median_time_to_merge_hours=10.0,
            avg_review_rounds=3.0,
            avg_pr_size=200,
            total_prs_analyzed=10,
        )
        result = identify_bottlenecks(velocity, [])
        assert any("review churn" in b for b in result)

    def test_large_prs(self):
        velocity = VelocitySignal(
            avg_time_to_merge_hours=12.0,
            median_time_to_merge_hours=10.0,
            avg_review_rounds=1.0,
            avg_pr_size=800,
            total_prs_analyzed=10,
        )
        result = identify_bottlenecks(velocity, [])
        assert any("Large PRs" in b for b in result)

    def test_no_bottlenecks(self):
        velocity = VelocitySignal(
            avg_time_to_merge_hours=12.0,
            median_time_to_merge_hours=10.0,
            avg_review_rounds=1.0,
            avg_pr_size=200,
            total_prs_analyzed=10,
        )
        result = identify_bottlenecks(velocity, [])
        assert any("No major" in b for b in result)

    def test_none_velocity(self):
        result = identify_bottlenecks(None, [])
        assert any("Insufficient" in b for b in result)


class TestPreemptiveFixes:
    def test_review_based_fixes(self):
        signals = [
            ReviewSignal("alice", "error_handling", 5),
            ReviewSignal("bob", "testing", 3),
        ]
        fixes = generate_preemptive_fixes(signals, [])
        assert len(fixes) >= 2
        assert "error handling" in fixes[0].lower()

    def test_ci_based_fixes(self):
        signals = [
            CISignal("lint", 10, 20, ["src/main.py"]),
        ]
        fixes = generate_preemptive_fixes([], signals)
        assert len(fixes) >= 1
        assert "lint" in fixes[0].lower()

    def test_empty_signals(self):
        fixes = generate_preemptive_fixes([], [])
        assert fixes == []


class TestRoutingRecs:
    def test_security_prs(self):
        prs = [
            _pr(1, title="Fix auth bug", files=["src/auth.py"]),
            _pr(2, title="Update session handling"),
        ]
        recs = generate_routing_recs(prs)
        sec_rec = next(
            (r for r in recs if "Security" in r["pattern"]),
            None,
        )
        assert sec_rec is not None
        assert sec_rec["model"] == "claude"
        assert sec_rec["validation"] == "codex"

    def test_test_only_prs(self):
        prs = [
            _pr(1, files=["tests/test_auth.py"]),
            _pr(2, files=["tests/test_main.py"]),
        ]
        recs = generate_routing_recs(prs)
        test_rec = next(
            (r for r in recs if "Test" in r["pattern"]),
            None,
        )
        assert test_rec is not None
        assert test_rec["model"] == "kimi"

    def test_empty_prs(self):
        recs = generate_routing_recs([])
        assert recs == []
