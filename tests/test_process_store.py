"""Tests for process intelligence SQLite store."""

import pytest
from pathlib import Path
import tempfile

from maggy.process.models import (
    ProcessReport,
    ReviewSignal,
    VelocitySignal,
)
from maggy.process.store import ProcessStore


@pytest.fixture
def store(tmp_path: Path) -> ProcessStore:
    return ProcessStore(tmp_path / "test_process.db")


class TestProcessStore:
    def test_save_and_load_pr_data(self, store):
        data = [{"number": 1, "title": "Test PR"}]
        store.save_pr_data("myproject", data)
        loaded = store.load_pr_data("myproject")
        assert loaded == data

    def test_load_pr_data_none(self, store):
        assert store.load_pr_data("noproject") is None

    def test_pr_data_overwrites(self, store):
        store.save_pr_data("proj", [{"v": 1}])
        store.save_pr_data("proj", [{"v": 2}])
        loaded = store.load_pr_data("proj")
        assert loaded == [{"v": 2}]

    def test_save_and_load_report(self, store):
        report = ProcessReport(
            project_key="api",
            generated_at="2026-01-01T00:00:00Z",
            total_prs=100,
            velocity=VelocitySignal(
                avg_time_to_merge_hours=24.0,
                median_time_to_merge_hours=18.0,
                avg_review_rounds=1.5,
                avg_pr_size=200,
                total_prs_analyzed=80,
            ),
            review_signals=[
                ReviewSignal("alice", "testing", 5),
            ],
            summary="Test summary",
            preemptive_fixes=["Fix error handling"],
        )
        store.save_report(report)
        loaded = store.load_latest_report("api")
        assert loaded is not None
        assert loaded["total_prs"] == 100
        assert loaded["summary"] == "Test summary"

    def test_load_report_none(self, store):
        assert store.load_latest_report("nope") is None

    def test_multiple_reports(self, store):
        r1 = ProcessReport(
            project_key="api",
            generated_at="2026-01-01T00:00:00Z",
            total_prs=50,
        )
        r2 = ProcessReport(
            project_key="api",
            generated_at="2026-01-02T00:00:00Z",
            total_prs=100,
        )
        store.save_report(r1)
        store.save_report(r2)
        loaded = store.load_latest_report("api")
        assert loaded["total_prs"] == 100

    def test_project_isolation(self, store):
        store.save_pr_data("proj_a", [{"a": 1}])
        store.save_pr_data("proj_b", [{"b": 2}])
        assert store.load_pr_data("proj_a") == [{"a": 1}]
        assert store.load_pr_data("proj_b") == [{"b": 2}]
