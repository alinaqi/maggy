"""Tests for history analyzer, store, and service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maggy.history.models import (
    HistoryReport,
    ProviderUsage,
    SessionEntry,
    TimeDistribution,
)


# --- Test Data Fixtures ---


def _make_session(
    sid: str = "s1",
    provider: str = "claude",
    project: str = "myproj",
    prompts: int = 5,
    tools: int = 3,
    started: str = "2024-01-15T10:00:00+00:00",
    ended: str = "2024-01-15T10:30:00+00:00",
) -> SessionEntry:
    return SessionEntry(
        session_id=sid,
        provider=provider,
        project=project,
        started_at=started,
        ended_at=ended,
        prompt_count=prompts,
        tool_use_count=tools,
        models_used=["claude-sonnet-4"],
        topics=["auth", "tests"],
        summary="fix auth bug",
    )


@pytest.fixture
def sample_sessions() -> list[SessionEntry]:
    return [
        _make_session("s1", "claude", "proj-a", 10, 5,
                       "2024-01-15T10:00:00+00:00",
                       "2024-01-15T10:45:00+00:00"),
        _make_session("s2", "claude", "proj-a", 8, 3,
                       "2024-01-15T14:00:00+00:00",
                       "2024-01-15T14:20:00+00:00"),
        _make_session("s3", "codex", "proj-b", 5, 2,
                       "2024-01-16T09:00:00+00:00",
                       "2024-01-16T09:15:00+00:00"),
        _make_session("s4", "kimi", "proj-a", 3, 1,
                       "2024-01-16T22:00:00+00:00",
                       "2024-01-16T22:10:00+00:00"),
    ]


# --- Analyzer Tests ---


class TestAnalyzer:
    """Tests for history/analyzer.py functions."""

    def test_build_report_empty(self):
        from maggy.history.analyzer import build_report
        report = build_report([])
        assert report.total_sessions == 0
        assert report.total_prompts == 0
        assert report.providers == []

    def test_build_report_with_data(self, sample_sessions):
        from maggy.history.analyzer import build_report
        report = build_report(sample_sessions)
        assert report.total_sessions == 4
        assert report.total_prompts == 26
        assert len(report.providers) == 3

    def test_aggregate_by_provider(self, sample_sessions):
        from maggy.history.analyzer import aggregate_by_provider
        usage = aggregate_by_provider(sample_sessions)
        assert len(usage) == 3
        claude = next(u for u in usage if u.provider == "claude")
        assert claude.session_count == 2
        assert claude.prompt_count == 18

    def test_aggregate_by_project(self, sample_sessions):
        from maggy.history.analyzer import aggregate_by_project
        projects = aggregate_by_project(sample_sessions)
        proj_a = next(p for p in projects if p.project == "proj-a")
        assert proj_a.total_sessions == 3
        assert "claude" in proj_a.providers_used

    def test_compute_time_distribution(self, sample_sessions):
        from maggy.history.analyzer import compute_time_distribution
        dist = compute_time_distribution(sample_sessions)
        assert isinstance(dist, TimeDistribution)
        # s1 starts at hour 10, s4 at hour 22
        assert 10 in dist.by_hour
        assert 22 in dist.by_hour

    def test_detect_patterns(self, sample_sessions):
        from maggy.history.analyzer import detect_patterns
        patterns = detect_patterns(sample_sessions)
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        # Should produce human-readable strings
        assert all(isinstance(p, str) for p in patterns)

    def test_extract_top_topics(self, sample_sessions):
        from maggy.history.analyzer import extract_top_topics
        topics = extract_top_topics(sample_sessions)
        assert isinstance(topics, list)
        assert "auth" in topics


# --- Store Tests ---


class TestHistoryStore:
    """Tests for history/store.py."""

    def test_save_and_load_sessions(self, tmp_path: Path):
        from maggy.history.store import HistoryStore
        store = HistoryStore(tmp_path / "history.db")
        sessions = [_make_session("s1"), _make_session("s2")]
        store.save_sessions(sessions)
        loaded = store.load_sessions()
        assert len(loaded) == 2

    def test_load_sessions_by_provider(self, tmp_path: Path):
        from maggy.history.store import HistoryStore
        store = HistoryStore(tmp_path / "history.db")
        sessions = [
            _make_session("s1", "claude"),
            _make_session("s2", "codex"),
        ]
        store.save_sessions(sessions)
        claude = store.load_sessions(provider="claude")
        assert len(claude) == 1
        assert claude[0]["provider"] == "claude"

    def test_save_and_load_report(self, tmp_path: Path):
        from maggy.history.store import HistoryStore
        store = HistoryStore(tmp_path / "history.db")
        report = HistoryReport(
            generated_at="2024-01-15T00:00:00Z",
            total_sessions=5,
            total_prompts=50,
            summary="test report",
        )
        store.save_report(report)
        loaded = store.load_latest_report()
        assert loaded is not None
        assert loaded["total_sessions"] == 5

    def test_load_report_empty(self, tmp_path: Path):
        from maggy.history.store import HistoryStore
        store = HistoryStore(tmp_path / "history.db")
        assert store.load_latest_report() is None


# --- Service Tests ---


class TestHistoryService:
    """Tests for history/service.py."""

    def _isolated_dirs(self, tmp_path: Path) -> dict:
        """Return CLI dirs that don't exist to isolate tests."""
        return {
            "claude": tmp_path / "no_claude",
            "codex": tmp_path / "no_codex",
            "kimi": tmp_path / "no_kimi",
        }

    def test_analyze_no_parsers(self, tmp_path: Path):
        from maggy.history.service import HistoryService
        svc = HistoryService(
            db_path=tmp_path / "history.db",
            cli_dirs=self._isolated_dirs(tmp_path),
        )
        report = svc.analyze()
        assert report.total_sessions == 0

    def test_analyze_with_claude(self, tmp_path: Path):
        from maggy.history.service import HistoryService
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        lines = [
            json.dumps({"display": "fix", "project": "/p", "sessionId": "s1", "timestamp": 1700000000000}),
            json.dumps({"display": "test", "project": "/p", "sessionId": "s1", "timestamp": 1700000300000}),
        ]
        (claude_dir / "history.jsonl").write_text("\n".join(lines) + "\n")
        dirs = self._isolated_dirs(tmp_path)
        dirs["claude"] = claude_dir
        svc = HistoryService(
            db_path=tmp_path / "history.db",
            cli_dirs=dirs,
        )
        report = svc.analyze()
        assert report.total_sessions == 1
        assert report.total_prompts == 2

    def test_get_report_cached(self, tmp_path: Path):
        from maggy.history.service import HistoryService
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        lines = [
            json.dumps({"display": "x", "project": "/p", "sessionId": "s1", "timestamp": 1700000000000}),
        ]
        (claude_dir / "history.jsonl").write_text("\n".join(lines) + "\n")
        dirs = self._isolated_dirs(tmp_path)
        dirs["claude"] = claude_dir
        svc = HistoryService(
            db_path=tmp_path / "history.db",
            cli_dirs=dirs,
        )
        svc.analyze()
        cached = svc.get_report()
        assert cached is not None
        assert cached["total_sessions"] == 1

    def test_get_sessions(self, tmp_path: Path):
        from maggy.history.service import HistoryService
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        lines = [
            json.dumps({"display": "x", "project": "/p", "sessionId": "s1", "timestamp": 1700000000000}),
        ]
        (claude_dir / "history.jsonl").write_text("\n".join(lines) + "\n")
        dirs = self._isolated_dirs(tmp_path)
        dirs["claude"] = claude_dir
        svc = HistoryService(
            db_path=tmp_path / "history.db",
            cli_dirs=dirs,
        )
        svc.analyze()
        sessions = svc.get_sessions()
        assert len(sessions) == 1
