"""Tests for chat context builder."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from maggy.services.chat_context import (
    _format_recent_prompts,
    _match_from_report,
    _match_history,
    _path_candidates,
    build_project_context,
    resolve_claude_session_id,
)


class TestPathCandidates:
    """Test path candidate generation."""

    def test_basic_path(self):
        result = _path_candidates(
            "/Users/ali/Documents/protaige", "protaige"
        )
        assert "protaige" in result
        assert "Documents" not in result  # skipped
        assert "Users" not in result  # skipped
        assert "ali" in result

    def test_nested_path(self):
        result = _path_candidates(
            "/Users/ali/Documents/AI-Playground/"
            "claude-skills-package",
            "claude-skills-package",
        )
        assert "claude-skills-package" in result
        assert "AI-Playground" in result

    def test_empty_path(self):
        result = _path_candidates("", "my-project")
        assert "my-project" in result


class TestMatchFromReport:
    """Test matching via aggregated report data."""

    def test_exact_project_match(self):
        report = {
            "projects": [
                {
                    "project": "protaige",
                    "total_sessions": 22,
                    "total_prompts": 2369,
                    "providers_used": ["claude"],
                    "top_topics": ["maia", "api", "auth"],
                },
            ],
        }
        result = _match_from_report(
            report, "/Users/ali/protaige", "protaige"
        )
        assert "22 sessions" in result
        assert "2369 prompts" in result
        assert "maia" in result

    def test_parent_dir_match(self):
        """Match claude-skills-package via AI-Playground."""
        report = {
            "projects": [
                {
                    "project": "AI-Playground",
                    "total_sessions": 5,
                    "total_prompts": 51,
                    "providers_used": ["claude"],
                    "top_topics": ["setup", "config"],
                },
            ],
        }
        result = _match_from_report(
            report,
            "/Users/ali/Documents/AI-Playground/"
            "claude-skills-package",
            "claude-skills-package",
        )
        assert "5 sessions" in result
        assert "51 prompts" in result

    def test_multiple_matches(self):
        """Match both direct and parent entries."""
        report = {
            "projects": [
                {
                    "project": "plugins",
                    "total_sessions": 22,
                    "total_prompts": 990,
                    "providers_used": ["claude"],
                    "top_topics": ["plugin"],
                },
                {
                    "project": "edubites",
                    "total_sessions": 10,
                    "total_prompts": 200,
                    "providers_used": ["claude"],
                    "top_topics": ["platform"],
                },
            ],
        }
        result = _match_from_report(
            report,
            "/Users/ali/edubites/plugins",
            "plugins",
        )
        assert "plugins" in result or "22 sessions" in result
        assert "edubites" in result or "10 sessions" in result

    def test_no_match(self):
        report = {
            "projects": [
                {"project": "unrelated", "total_sessions": 1,
                 "total_prompts": 5, "providers_used": [],
                 "top_topics": []},
            ],
        }
        result = _match_from_report(
            report, "/Users/ali/my-project", "my-project"
        )
        assert result == ""


class TestMatchHistory:
    """Test the main matching function."""

    def test_uses_report_when_available(self):
        history = MagicMock()
        history.get_report.return_value = {
            "projects": [
                {
                    "project": "myapp",
                    "total_sessions": 5,
                    "total_prompts": 100,
                    "providers_used": ["claude"],
                    "top_topics": ["api"],
                },
            ],
        }
        result = _match_history(
            history, "/Users/ali/myapp", "myapp"
        )
        assert "5 sessions" in result

    def test_returns_empty_when_no_history(self):
        result = _match_history(
            None, "/some/path", "proj"
        )
        assert result == ""

    def test_returns_empty_when_no_report(self):
        history = MagicMock()
        history.get_report.return_value = None
        result = _match_history(
            history, "/some/path", "proj"
        )
        assert result == ""


class TestFormatRecentPrompts:
    """Test recent prompt formatting."""

    def test_matching_prompts(self):
        prompts = [
            {"project": "protaige", "text": "fix the auth bug",
             "timestamp": "2026-05-10T14:00:00"},
            {"project": "other", "text": "unrelated",
             "timestamp": "2026-05-10T13:00:00"},
        ]
        result = _format_recent_prompts(prompts, "protaige")
        assert "fix the auth bug" in result
        assert "unrelated" not in result

    def test_no_matching_prompts(self):
        prompts = [
            {"project": "other", "text": "something",
             "timestamp": "2026-05-10T14:00:00"},
        ]
        result = _format_recent_prompts(prompts, "protaige")
        assert result == ""

    def test_limits_to_five(self):
        prompts = [
            {"project": "x", "text": f"msg {i}",
             "timestamp": f"2026-05-10T1{i}:00:00"}
            for i in range(10)
        ]
        result = _format_recent_prompts(prompts, "x")
        assert result.count("- [") == 5


class TestResolveSessionId:
    """Test Claude session ID resolution."""

    def test_finds_session_id(self, tmp_path):
        history = tmp_path / ".claude" / "history.jsonl"
        history.parent.mkdir(parents=True)
        entries = [
            json.dumps({
                "project": "/Users/ali/protaige",
                "sessionId": "abc-123",
                "timestamp": 1715000000000,
            }),
            json.dumps({
                "project": "/Users/ali/protaige",
                "sessionId": "def-456",
                "timestamp": 1715100000000,
            }),
        ]
        history.write_text("\n".join(entries))
        from unittest.mock import patch
        with patch(
            "maggy.services.chat_context.Path.home",
            return_value=tmp_path,
        ):
            result = resolve_claude_session_id(
                "/Users/ali/protaige"
            )
        assert result == "def-456"

    def test_no_match(self, tmp_path):
        history = tmp_path / ".claude" / "history.jsonl"
        history.parent.mkdir(parents=True)
        history.write_text(json.dumps({
            "project": "/Users/ali/other",
            "sessionId": "xyz",
            "timestamp": 1715000000000,
        }))
        from unittest.mock import patch
        with patch(
            "maggy.services.chat_context.Path.home",
            return_value=tmp_path,
        ):
            result = resolve_claude_session_id(
                "/Users/ali/protaige"
            )
        assert result == ""

    def test_missing_file(self, tmp_path):
        from unittest.mock import patch
        with patch(
            "maggy.services.chat_context.Path.home",
            return_value=tmp_path,
        ):
            result = resolve_claude_session_id("/some/path")
        assert result == ""


class TestBuildProjectContext:
    """Test full context assembly."""

    def test_combines_history_and_prompts(self):
        history = MagicMock()
        history.get_report.return_value = {
            "projects": [
                {
                    "project": "myapp",
                    "total_sessions": 8,
                    "total_prompts": 200,
                    "providers_used": ["claude"],
                    "top_topics": ["api", "auth"],
                },
            ],
        }
        prompts = [
            {"project": "myapp", "text": "add endpoint",
             "timestamp": "2026-05-10T14:00:00"},
        ]
        result = build_project_context(
            history, "/Users/ali/myapp", "myapp", prompts,
        )
        assert "8 sessions" in result
        assert "add endpoint" in result

    def test_empty_when_nothing(self):
        history = MagicMock()
        history.get_report.return_value = {"projects": []}
        result = build_project_context(
            history, "/some/path", "proj", [],
        )
        assert result == ""
