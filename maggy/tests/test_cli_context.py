"""Tests for cli_context — CLI history context gathering."""
from __future__ import annotations

from maggy.cli_context import (
    _format_sessions,
    _matches_project,
    gather_cli_context,
)


def test_matches_project_exact():
    assert _matches_project(
        {"project": "/tmp/foo"}, "/tmp/foo",
    )


def test_matches_project_trailing_slash():
    assert _matches_project(
        {"project": "/tmp/foo/"}, "/tmp/foo",
    )


def test_matches_project_basename():
    assert _matches_project(
        {"project": "foo"}, "/tmp/foo",
    )


def test_matches_project_no_match():
    assert not _matches_project(
        {"project": "bar"}, "/tmp/foo",
    )


def test_format_sessions_empty():
    assert _format_sessions([], "/tmp/foo") == ""


def test_format_sessions_filters_by_project():
    sessions = [
        {"provider": "claude", "project": "foo",
         "prompt_count": 5, "started_at": "2026-01-01",
         "summary": "worked on auth"},
        {"provider": "kimi", "project": "bar",
         "prompt_count": 3, "started_at": "2026-01-02",
         "summary": "different project"},
    ]
    result = _format_sessions(sessions, "/tmp/foo")
    assert "claude" in result
    assert "5 prompts" in result
    assert "kimi" not in result


def test_format_sessions_includes_summary():
    sessions = [
        {"provider": "codex", "project": "myproj",
         "prompt_count": 2, "started_at": "2026-05-13",
         "summary": "fixed the bug"},
    ]
    result = _format_sessions(sessions, "/tmp/myproj")
    assert "fixed the bug" in result
    assert "codex" in result


def test_gather_no_history(monkeypatch):
    """Returns empty when HistoryService unavailable."""
    result = gather_cli_context("/nonexistent")
    assert result == ""
