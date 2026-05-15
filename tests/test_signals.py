"""Tests for signal extraction from PR data."""

import pytest

from maggy.process.models import (
    CheckRecord,
    PRRecord,
    ReviewRecord,
)
from maggy.process.signals import (
    extract_ci_signals,
    extract_review_signals,
    extract_velocity_signals,
)


def _pr(
    number: int = 1,
    reviews: list | None = None,
    checks: list | None = None,
    files: list | None = None,
    state: str = "merged",
    created_at: str = "2026-01-01T00:00:00Z",
    merged_at: str | None = "2026-01-02T00:00:00Z",
    additions: int = 50,
    deletions: int = 10,
) -> PRRecord:
    return PRRecord(
        number=number,
        title=f"PR #{number}",
        author="dev",
        state=state,
        created_at=created_at,
        merged_at=merged_at,
        additions=additions,
        deletions=deletions,
        changed_files=3,
        head_sha="abc",
        base_branch="main",
        reviews=reviews or [],
        checks=checks or [],
        files=files or [],
    )


class TestReviewSignals:
    def test_detects_recurring_theme(self):
        prs = [
            _pr(1, reviews=[
                ReviewRecord("alice", "COMMENTED", "Missing error handling here", ""),
            ]),
            _pr(2, reviews=[
                ReviewRecord("alice", "COMMENTED", "Add error handling for edge case", ""),
            ]),
            _pr(3, reviews=[
                ReviewRecord("alice", "COMMENTED", "No error handling", ""),
            ]),
        ]
        signals = extract_review_signals(prs)
        assert len(signals) >= 1
        assert signals[0].reviewer == "alice"
        assert signals[0].theme == "error_handling"
        assert signals[0].count >= 2

    def test_ignores_single_occurrence(self):
        prs = [
            _pr(1, reviews=[
                ReviewRecord("bob", "COMMENTED", "Fix error handling", ""),
            ]),
        ]
        signals = extract_review_signals(prs)
        assert len(signals) == 0

    def test_empty_reviews(self):
        prs = [_pr(1)]
        signals = extract_review_signals(prs)
        assert signals == []

    def test_multiple_reviewers(self):
        prs = [
            _pr(1, reviews=[
                ReviewRecord("alice", "COMMENTED", "Add tests please", ""),
                ReviewRecord("bob", "COMMENTED", "Missing test coverage", ""),
            ]),
            _pr(2, reviews=[
                ReviewRecord("alice", "COMMENTED", "Where are the tests?", ""),
                ReviewRecord("bob", "COMMENTED", "Add test for edge case", ""),
            ]),
        ]
        signals = extract_review_signals(prs)
        reviewers = {s.reviewer for s in signals}
        assert "alice" in reviewers
        assert "bob" in reviewers


class TestCISignals:
    def test_detects_failures(self):
        prs = [
            _pr(1, checks=[
                CheckRecord("lint", "success", "", ""),
                CheckRecord("test", "failure", "", ""),
            ], files=["src/auth.py"]),
            _pr(2, checks=[
                CheckRecord("lint", "success", "", ""),
                CheckRecord("test", "failure", "", ""),
            ], files=["src/auth.py"]),
        ]
        signals = extract_ci_signals(prs)
        test_sig = next(
            s for s in signals if s.check_name == "test"
        )
        assert test_sig.failure_count == 2
        assert test_sig.failure_rate == 1.0

    def test_no_failures_no_signals(self):
        prs = [
            _pr(1, checks=[
                CheckRecord("lint", "success", "", ""),
            ]),
        ]
        signals = extract_ci_signals(prs)
        assert signals == []


class TestVelocitySignals:
    def test_basic_velocity(self):
        prs = [
            _pr(1, created_at="2026-01-01T00:00:00Z",
                 merged_at="2026-01-02T00:00:00Z",
                 additions=100, deletions=50),
            _pr(2, created_at="2026-01-03T00:00:00Z",
                 merged_at="2026-01-04T12:00:00Z",
                 additions=200, deletions=100),
        ]
        v = extract_velocity_signals(prs)
        assert v is not None
        assert v.total_prs_analyzed == 2
        assert v.avg_time_to_merge_hours > 0
        assert v.avg_pr_size > 0

    def test_no_merged_prs(self):
        prs = [_pr(1, state="open", merged_at=None)]
        v = extract_velocity_signals(prs)
        assert v is None

    def test_empty_list(self):
        v = extract_velocity_signals([])
        assert v is None
