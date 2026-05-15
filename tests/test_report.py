"""Tests for report generation."""

import pytest

from maggy.process.models import (
    CISignal,
    ProcessReport,
    ReviewSignal,
    VelocitySignal,
)
from maggy.process.report import (
    format_health_metrics,
    generate_summary,
)


def _report(**overrides) -> ProcessReport:
    defaults = {
        "project_key": "api",
        "generated_at": "2026-01-01T00:00:00Z",
        "total_prs": 100,
    }
    defaults.update(overrides)
    return ProcessReport(**defaults)


class TestGenerateSummary:
    def test_basic_summary(self):
        report = _report(
            velocity=VelocitySignal(
                avg_time_to_merge_hours=24.0,
                median_time_to_merge_hours=18.0,
                avg_review_rounds=1.5,
                avg_pr_size=200,
                total_prs_analyzed=80,
            ),
        )
        summary = generate_summary(report)
        assert "api" in summary
        assert "24.0h" in summary
        assert "100 PRs" in summary

    def test_review_signals_in_summary(self):
        report = _report(
            review_signals=[
                ReviewSignal("alice", "testing", 5),
            ],
        )
        summary = generate_summary(report)
        assert "alice" in summary
        assert "testing" in summary

    def test_ci_signals_in_summary(self):
        report = _report(
            ci_signals=[
                CISignal("lint", 10, 50),
            ],
        )
        summary = generate_summary(report)
        assert "lint" in summary

    def test_empty_report(self):
        report = _report()
        summary = generate_summary(report)
        assert "api" in summary

    def test_fixes_in_summary(self):
        report = _report(
            preemptive_fixes=["Add error handling"],
        )
        summary = generate_summary(report)
        assert "error handling" in summary


class TestHealthMetrics:
    def test_healthy_status(self):
        velocity = VelocitySignal(
            avg_time_to_merge_hours=12.0,
            median_time_to_merge_hours=10.0,
            avg_review_rounds=1.0,
            avg_pr_size=150,
            total_prs_analyzed=50,
        )
        ci = [CISignal("test", 1, 50)]
        health = format_health_metrics(velocity, ci, [])
        assert health["status"] == "healthy"

    def test_needs_attention(self):
        velocity = VelocitySignal(
            avg_time_to_merge_hours=72.0,
            median_time_to_merge_hours=60.0,
            avg_review_rounds=3.5,
            avg_pr_size=800,
            total_prs_analyzed=50,
        )
        ci = [CISignal("test", 20, 50)]
        health = format_health_metrics(velocity, ci, [])
        assert health["status"] == "needs_attention"

    def test_no_velocity(self):
        health = format_health_metrics(None, [], [])
        assert health["status"] == "unknown"

    def test_ci_pass_rate(self):
        ci = [
            CISignal("lint", 5, 100),
            CISignal("test", 10, 100),
        ]
        health = format_health_metrics(None, ci, [])
        assert health["ci_pass_rate"] == 0.925
