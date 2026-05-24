"""Tests for CLI session refresh service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maggy.services.refresh import (
    RefreshService,
    SessionDigest,
    _extract_conversation,
    _find_recent_sessions,
    _path_matches,
)


@pytest.fixture
def claude_dir(tmp_path):
    projects = tmp_path / "projects"
    proj_dir = projects / "-Users-test-myproject"
    proj_dir.mkdir(parents=True)
    return tmp_path


def _write_history(claude_dir, entries):
    path = claude_dir / "history.jsonl"
    lines = [json.dumps(e) for e in entries]
    path.write_text("\n".join(lines))


def _write_conversation(claude_dir, project_slug, session_id, messages):
    proj_dir = claude_dir / "projects" / project_slug
    proj_dir.mkdir(parents=True, exist_ok=True)
    path = proj_dir / f"{session_id}.jsonl"
    lines = [json.dumps(m) for m in messages]
    path.write_text("\n".join(lines))


class TestPathMatches:
    def test_exact_match(self):
        assert _path_matches("/Users/test/proj", "/Users/test/proj")

    def test_subdirectory(self):
        assert _path_matches("/Users/test/proj/sub", "/Users/test/proj")

    def test_parent_matches(self):
        assert _path_matches("/Users/test/proj", "/Users/test/proj/sub")

    def test_no_match(self):
        assert not _path_matches("/Users/test/other", "/Users/test/proj")

    def test_trailing_slash(self):
        assert _path_matches("/Users/test/proj/", "/Users/test/proj")


class TestFindRecentSessions:
    def test_finds_sessions(self, claude_dir):
        _write_history(claude_dir, [
            {"display": "fix the bug", "timestamp": "1000000",
             "project": "/Users/test/myproject", "sessionId": "s1"},
            {"display": "add tests", "timestamp": "2000000",
             "project": "/Users/test/myproject", "sessionId": "s1"},
            {"display": "deploy it", "timestamp": "3000000",
             "project": "/Users/test/other", "sessionId": "s2"},
        ])
        sessions = _find_recent_sessions(claude_dir, limit=5)
        assert len(sessions) == 2
        assert sessions[0]["session_id"] == "s2"
        assert sessions[0]["last_prompt"] == "deploy it"

    def test_dedupes_by_session_id(self, claude_dir):
        _write_history(claude_dir, [
            {"display": "first", "timestamp": "1000",
             "project": "/Users/test/proj", "sessionId": "s1"},
            {"display": "second", "timestamp": "2000",
             "project": "/Users/test/proj", "sessionId": "s1"},
        ])
        sessions = _find_recent_sessions(claude_dir, limit=5)
        assert len(sessions) == 1
        assert sessions[0]["last_prompt"] == "second"

    def test_filters_by_project_path(self, claude_dir):
        _write_history(claude_dir, [
            {"display": "fix bug", "timestamp": "1000",
             "project": "/Users/test/myproject", "sessionId": "s1"},
            {"display": "deploy", "timestamp": "2000",
             "project": "/Users/test/other", "sessionId": "s2"},
            {"display": "test", "timestamp": "3000",
             "project": "/Users/test/myproject", "sessionId": "s3"},
        ])
        sessions = _find_recent_sessions(
            claude_dir, limit=5,
            project_path="/Users/test/myproject",
        )
        assert len(sessions) == 2
        ids = {s["session_id"] for s in sessions}
        assert ids == {"s1", "s3"}

    def test_empty_history(self, claude_dir):
        assert _find_recent_sessions(claude_dir, limit=5) == []


class TestExtractConversation:
    def test_extracts_user_and_assistant(self, claude_dir):
        slug = "-Users-test-myproject"
        _write_conversation(claude_dir, slug, "s1", [
            {"type": "user", "message": {"content": [
                {"type": "text", "text": "fix the auth bug"},
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "I found the issue in login.py"},
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "tool_use", "name": "Edit", "input": {}},
            ]}},
            {"type": "user", "message": {"content": [
                {"type": "tool_result", "content": "ok"},
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Fixed. The session token was stale."},
            ]}},
        ])
        turns = _extract_conversation(claude_dir, slug, "s1", max_turns=10)
        assert len(turns) == 3
        assert turns[0] == {"role": "user", "text": "fix the auth bug"}
        assert turns[1] == {"role": "assistant", "text": "I found the issue in login.py"}
        assert turns[2] == {"role": "assistant", "text": "Fixed. The session token was stale."}

    def test_limits_turns(self, claude_dir):
        slug = "-Users-test-proj"
        msgs = []
        for i in range(20):
            msgs.append({"type": "user", "message": {"content": [
                {"type": "text", "text": f"prompt {i}"},
            ]}})
            msgs.append({"type": "assistant", "message": {"content": [
                {"type": "text", "text": f"reply {i}"},
            ]}})
        _write_conversation(claude_dir, slug, "s1", msgs)
        turns = _extract_conversation(claude_dir, slug, "s1", max_turns=6)
        assert len(turns) == 6

    def test_missing_file_returns_empty(self, claude_dir):
        turns = _extract_conversation(claude_dir, "nope", "s1", max_turns=10)
        assert turns == []


class TestRefreshService:
    def test_refresh_returns_digests(self, claude_dir):
        _write_history(claude_dir, [
            {"display": "add pipeline", "timestamp": "5000000",
             "project": "/Users/test/maggy", "sessionId": "abc"},
        ])
        slug = "-Users-test-maggy"
        _write_conversation(claude_dir, slug, "abc", [
            {"type": "user", "message": {"content": [
                {"type": "text", "text": "add the pipeline orchestrator"},
            ]}},
            {"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Created pipeline/orchestrator.py with ChatPipeline class."},
            ]}},
        ])
        svc = RefreshService(claude_dir=claude_dir)
        digests = svc.refresh(limit=3)
        assert len(digests) == 1
        d = digests[0]
        assert isinstance(d, SessionDigest)
        assert d.session_id == "abc"
        assert d.project == "maggy"
        assert len(d.turns) == 2
        assert d.cli == "claude"

    def test_refresh_empty(self, claude_dir):
        svc = RefreshService(claude_dir=claude_dir)
        digests = svc.refresh(limit=3)
        assert digests == []
