"""Tests for CLI history parsers — Claude, Codex, Kimi."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from maggy.history.parsers.claude import ClaudeHistoryParser
from maggy.history.parsers.codex import CodexHistoryParser
from maggy.history.parsers.kimi import KimiHistoryParser


# --- Claude Parser ---


class TestClaudeParser:
    """Tests for ClaudeHistoryParser."""

    def test_not_available_missing_dir(self, tmp_path: Path):
        p = ClaudeHistoryParser(tmp_path / ".claude")
        assert p.is_available() is False

    def test_available_with_history(self, tmp_path: Path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "history.jsonl").write_text("")
        p = ClaudeHistoryParser(claude_dir)
        assert p.is_available() is True

    def test_session_count_empty(self, tmp_path: Path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "history.jsonl").write_text("")
        p = ClaudeHistoryParser(claude_dir)
        assert p.session_count() == 0

    def test_session_count(self, tmp_path: Path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        lines = [
            json.dumps({"display": "fix bug", "project": "/p", "sessionId": "s1", "timestamp": 1700000000000}),
            json.dumps({"display": "add test", "project": "/p", "sessionId": "s1", "timestamp": 1700000100000}),
            json.dumps({"display": "deploy", "project": "/q", "sessionId": "s2", "timestamp": 1700001000000}),
        ]
        (claude_dir / "history.jsonl").write_text("\n".join(lines) + "\n")
        p = ClaudeHistoryParser(claude_dir)
        assert p.session_count() == 2

    def test_parse_sessions(self, tmp_path: Path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        lines = [
            json.dumps({"display": "fix auth", "project": "/Users/test/proj", "sessionId": "s1", "timestamp": 1700000000000}),
            json.dumps({"display": "add tests", "project": "/Users/test/proj", "sessionId": "s1", "timestamp": 1700000300000}),
            json.dumps({"display": "deploy app", "project": "/Users/test/other", "sessionId": "s2", "timestamp": 1700001000000}),
        ]
        (claude_dir / "history.jsonl").write_text("\n".join(lines) + "\n")
        p = ClaudeHistoryParser(claude_dir)
        sessions = p.parse_sessions(limit=10)
        assert len(sessions) == 2
        s1 = next(s for s in sessions if s.session_id == "s1")
        assert s1.provider == "claude"
        assert s1.prompt_count == 2
        assert s1.summary == "fix auth"
        assert "proj" in s1.project

    def test_parse_empty_history(self, tmp_path: Path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "history.jsonl").write_text("")
        p = ClaudeHistoryParser(claude_dir)
        assert p.parse_sessions() == []

    def test_parse_with_transcript(self, tmp_path: Path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        lines = [
            json.dumps({"display": "task1", "project": "/Users/test/proj", "sessionId": "s1", "timestamp": 1700000000000}),
        ]
        (claude_dir / "history.jsonl").write_text("\n".join(lines) + "\n")
        # Create transcript directory
        proj_dir = claude_dir / "projects" / "-Users-test-proj"
        proj_dir.mkdir(parents=True)
        transcript = [
            json.dumps({"type": "user", "message": {"role": "user", "content": "fix the bug"}, "sessionId": "s1", "timestamp": 1700000000000, "gitBranch": "feat/auth"}),
            json.dumps({"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}, {"type": "tool_use", "name": "read"}]}, "model": "claude-sonnet-4", "timestamp": 1700000010000}),
        ]
        (proj_dir / "s1.jsonl").write_text("\n".join(transcript) + "\n")
        p = ClaudeHistoryParser(claude_dir)
        sessions = p.parse_sessions()
        assert len(sessions) == 1
        s = sessions[0]
        assert s.tool_use_count >= 1
        assert "claude-sonnet-4" in s.models_used
        assert s.git_branch == "feat/auth"


# --- Codex Parser ---


class TestCodexParser:
    """Tests for CodexHistoryParser."""

    def test_not_available_missing_dir(self, tmp_path: Path):
        p = CodexHistoryParser(tmp_path / ".codex")
        assert p.is_available() is False

    def test_available_with_index(self, tmp_path: Path):
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        (codex_dir / "session_index.jsonl").write_text("")
        p = CodexHistoryParser(codex_dir)
        assert p.is_available() is True

    def test_session_count(self, tmp_path: Path):
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        lines = [
            json.dumps({"id": "s1", "thread_name": "fix bug", "updated_at": "2024-01-01T00:00:00Z"}),
            json.dumps({"id": "s2", "thread_name": "add feature", "updated_at": "2024-01-02T00:00:00Z"}),
        ]
        (codex_dir / "session_index.jsonl").write_text("\n".join(lines) + "\n")
        p = CodexHistoryParser(codex_dir)
        assert p.session_count() == 2

    def test_parse_sessions(self, tmp_path: Path):
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        index_lines = [
            json.dumps({"id": "s1", "thread_name": "fix auth bug", "updated_at": "2024-01-01T10:00:00Z"}),
        ]
        (codex_dir / "session_index.jsonl").write_text("\n".join(index_lines) + "\n")
        history_lines = [
            json.dumps({"session_id": "s1", "ts": 1704100000, "text": "fix the auth bug"}),
            json.dumps({"session_id": "s1", "ts": 1704100300, "text": "now add tests"}),
        ]
        (codex_dir / "history.jsonl").write_text("\n".join(history_lines) + "\n")
        p = CodexHistoryParser(codex_dir)
        sessions = p.parse_sessions()
        assert len(sessions) == 1
        s = sessions[0]
        assert s.provider == "codex"
        assert s.prompt_count == 2
        assert s.summary == "fix auth bug"

    def test_parse_empty(self, tmp_path: Path):
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        (codex_dir / "session_index.jsonl").write_text("")
        (codex_dir / "history.jsonl").write_text("")
        p = CodexHistoryParser(codex_dir)
        assert p.parse_sessions() == []


# --- Kimi Parser ---


class TestKimiParser:
    """Tests for KimiHistoryParser."""

    def test_not_available_missing_dir(self, tmp_path: Path):
        p = KimiHistoryParser(tmp_path / ".kimi")
        assert p.is_available() is False

    def test_available_with_sessions(self, tmp_path: Path):
        kimi_dir = tmp_path / ".kimi"
        (kimi_dir / "sessions").mkdir(parents=True)
        p = KimiHistoryParser(kimi_dir)
        assert p.is_available() is True

    def test_session_count(self, tmp_path: Path):
        kimi_dir = tmp_path / ".kimi"
        sess_dir = kimi_dir / "sessions" / "abc" / "uuid1"
        sess_dir.mkdir(parents=True)
        (sess_dir / "context.jsonl").write_text("")
        sess_dir2 = kimi_dir / "sessions" / "abc" / "uuid2"
        sess_dir2.mkdir(parents=True)
        (sess_dir2 / "context.jsonl").write_text("")
        p = KimiHistoryParser(kimi_dir)
        assert p.session_count() == 2

    def test_parse_sessions(self, tmp_path: Path):
        kimi_dir = tmp_path / ".kimi"
        sess_dir = kimi_dir / "sessions" / "abc" / "uuid1"
        sess_dir.mkdir(parents=True)
        ctx_lines = [
            json.dumps({"role": "user", "content": "fix the deploy"}),
            json.dumps({"role": "assistant", "content": "sure"}),
            json.dumps({"role": "user", "content": "now test it"}),
        ]
        (sess_dir / "context.jsonl").write_text("\n".join(ctx_lines) + "\n")
        wire_lines = [
            json.dumps({"timestamp": 1700000000.0, "message": '{"type":"TurnBegin"}'}),
            json.dumps({"timestamp": 1700000010.0, "message": '{"type":"StepBegin"}'}),
            json.dumps({"timestamp": 1700000300.0, "message": '{"type":"TurnBegin"}'}),
        ]
        (sess_dir / "wire.jsonl").write_text("\n".join(wire_lines) + "\n")
        p = KimiHistoryParser(kimi_dir)
        sessions = p.parse_sessions()
        assert len(sessions) == 1
        s = sessions[0]
        assert s.provider == "kimi"
        assert s.prompt_count == 2
        assert s.tool_use_count >= 1
        assert s.summary == "fix the deploy"

    def test_parse_empty(self, tmp_path: Path):
        kimi_dir = tmp_path / ".kimi"
        (kimi_dir / "sessions").mkdir(parents=True)
        p = KimiHistoryParser(kimi_dir)
        assert p.parse_sessions() == []

    def test_parse_missing_wire(self, tmp_path: Path):
        """Graceful when wire.jsonl is missing."""
        kimi_dir = tmp_path / ".kimi"
        sess_dir = kimi_dir / "sessions" / "abc" / "uuid1"
        sess_dir.mkdir(parents=True)
        ctx_lines = [
            json.dumps({"role": "user", "content": "hello"}),
        ]
        (sess_dir / "context.jsonl").write_text("\n".join(ctx_lines) + "\n")
        p = KimiHistoryParser(kimi_dir)
        sessions = p.parse_sessions()
        assert len(sessions) == 1
        assert sessions[0].prompt_count == 1
