"""Tests for process intelligence dataclasses."""

import pytest

from maggy.process.models import (
    CheckRecord,
    ModelTier,
    PRRecord,
    ReviewRecord,
    VelocitySignal,
)


def _make_pr(**overrides) -> PRRecord:
    defaults = {
        "number": 1,
        "title": "Fix auth",
        "author": "ali",
        "state": "merged",
        "created_at": "2026-01-01T00:00:00Z",
        "merged_at": "2026-01-02T12:00:00Z",
        "additions": 50,
        "deletions": 10,
        "changed_files": 3,
        "head_sha": "abc123",
        "base_branch": "main",
    }
    defaults.update(overrides)
    return PRRecord(**defaults)


class TestPRRecord:
    def test_total_lines(self):
        pr = _make_pr(additions=100, deletions=30)
        assert pr.total_lines == 130

    def test_time_to_merge_hours(self):
        pr = _make_pr(
            created_at="2026-01-01T00:00:00Z",
            merged_at="2026-01-02T12:00:00Z",
        )
        assert pr.time_to_merge_hours == 36.0

    def test_time_to_merge_none_when_not_merged(self):
        pr = _make_pr(merged_at=None)
        assert pr.time_to_merge_hours is None

    def test_review_rounds(self):
        pr = _make_pr()
        pr.reviews = [
            ReviewRecord("r1", "CHANGES_REQUESTED", "", ""),
            ReviewRecord("r1", "APPROVED", "", ""),
            ReviewRecord("r2", "CHANGES_REQUESTED", "", ""),
        ]
        assert pr.review_rounds == 2

    def test_ci_passed_no_checks(self):
        pr = _make_pr()
        assert pr.ci_passed is True

    def test_ci_passed_all_success(self):
        pr = _make_pr()
        pr.checks = [
            CheckRecord("lint", "success", "", ""),
            CheckRecord("test", "success", "", ""),
        ]
        assert pr.ci_passed is True

    def test_ci_failed(self):
        pr = _make_pr()
        pr.checks = [
            CheckRecord("lint", "success", "", ""),
            CheckRecord("test", "failure", "", ""),
        ]
        assert pr.ci_passed is False


class TestModelTier:
    def test_defaults(self):
        tier = ModelTier(
            name="test",
            provider="test",
            model="test-1",
            cost_rank=1,
            complexity_min=0,
            complexity_max=5,
        )
        assert tier.role == "primary"
        assert tier.strengths == []
