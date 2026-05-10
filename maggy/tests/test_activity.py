"""Tests for CLI activity scanner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from maggy.services.activity import (
    ActiveSession,
    ActivityService,
    RecentPrompt,
    _parse_claude_processes,
    _recent_prompts,
)


class TestParseClaudeProcesses:
    def test_detects_running_session(self):
        lines = [
            "user  1234  0.0  0.1  claude --dangerously-skip-permissions --continue",
        ]
        with patch(
            "maggy.services.activity._get_cwd",
            return_value="/Users/me/proj-a",
        ):
            sessions = _parse_claude_processes(lines)
        assert len(sessions) == 1
        assert sessions[0].cli == "claude"
        assert sessions[0].pid == 1234
        assert sessions[0].status == "running"
        assert sessions[0].project == "proj-a"

    def test_detects_agent_subprocess(self):
        lines = [
            "user  5678  0.1  0.3  /path/to/claude "
            "--agent-id be-schema@maia-demo "
            "--agent-name be-schema "
            "--team-name maia-demo "
            "--parent-session-id abc-123",
        ]
        with patch(
            "maggy.services.activity._get_cwd",
            return_value="/Users/me/proj-b",
        ):
            sessions = _parse_claude_processes(lines)
        assert len(sessions) == 1
        s = sessions[0]
        assert s.status == "agent"
        assert s.agent_name == "be-schema"
        assert s.team_name == "maia-demo"

    def test_ignores_non_cli_processes(self):
        lines = [
            "user  9999  0.0  0.0  /Applications/Claude.app/Contents/MacOS/Claude",
            "user  8888  0.0  0.0  grep claude",
        ]
        sessions = _parse_claude_processes(lines)
        assert sessions == []

    def test_empty_input(self):
        assert _parse_claude_processes([]) == []


class TestRecentPrompts:
    def test_reads_claude_history(self, tmp_path: Path):
        history = tmp_path / "history.jsonl"
        entries = [
            {"display": "fix the bug", "timestamp": 1000, "project": "/Users/me/app", "sessionId": "s1"},
            {"display": "run tests", "timestamp": 2000, "project": "/Users/me/app", "sessionId": "s1"},
        ]
        history.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n",
        )
        prompts = _recent_prompts(
            claude_dir=tmp_path, codex_dir=tmp_path / "none",
            kimi_dir=tmp_path / "none2", limit=5,
        )
        assert len(prompts) == 2
        assert prompts[0].text == "run tests"
        assert prompts[0].cli == "claude"
        assert prompts[0].project == "app"

    def test_reads_codex_history(self, tmp_path: Path):
        history = tmp_path / "history.jsonl"
        entries = [
            {"session_id": "c1", "ts": 3000, "text": "deploy it"},
        ]
        history.write_text(
            "\n".join(json.dumps(e) for e in entries) + "\n",
        )
        prompts = _recent_prompts(
            claude_dir=tmp_path / "none", codex_dir=tmp_path,
            kimi_dir=tmp_path / "none2", limit=5,
        )
        assert len(prompts) == 1
        assert prompts[0].cli == "codex"
        assert prompts[0].text == "deploy it"

    def test_merges_and_sorts_by_time(self, tmp_path: Path):
        claude_dir = tmp_path / "claude"
        codex_dir = tmp_path / "codex"
        claude_dir.mkdir()
        codex_dir.mkdir()
        (claude_dir / "history.jsonl").write_text(
            json.dumps({"display": "old", "timestamp": 1000, "project": "/p", "sessionId": "s"}) + "\n",
        )
        (codex_dir / "history.jsonl").write_text(
            json.dumps({"session_id": "c1", "ts": 5000, "text": "new"}) + "\n",
        )
        prompts = _recent_prompts(
            claude_dir=claude_dir, codex_dir=codex_dir,
            kimi_dir=tmp_path / "none", limit=5,
        )
        assert prompts[0].text == "new"
        assert prompts[1].text == "old"

    def test_limits_output(self, tmp_path: Path):
        history = tmp_path / "history.jsonl"
        lines = []
        for i in range(20):
            lines.append(json.dumps({
                "display": f"msg-{i}", "timestamp": i * 1000,
                "project": "/p", "sessionId": "s",
            }))
        history.write_text("\n".join(lines) + "\n")
        prompts = _recent_prompts(
            claude_dir=tmp_path, codex_dir=tmp_path / "x",
            kimi_dir=tmp_path / "y", limit=5,
        )
        assert len(prompts) == 5

    def test_no_history_files(self, tmp_path: Path):
        prompts = _recent_prompts(
            claude_dir=tmp_path / "a", codex_dir=tmp_path / "b",
            kimi_dir=tmp_path / "c", limit=5,
        )
        assert prompts == []

    def test_malformed_json_skipped(self, tmp_path: Path):
        history = tmp_path / "history.jsonl"
        history.write_text(
            "not-json\n"
            + json.dumps({"display": "ok", "timestamp": 1000, "project": "/p", "sessionId": "s"})
            + "\n",
        )
        prompts = _recent_prompts(
            claude_dir=tmp_path, codex_dir=tmp_path / "x",
            kimi_dir=tmp_path / "y", limit=5,
        )
        assert len(prompts) == 1
        assert prompts[0].text == "ok"


class TestActivityService:
    def test_get_activity_shape(self):
        svc = ActivityService()
        with patch(
            "maggy.services.activity._scan_processes",
            return_value=[],
        ), patch(
            "maggy.services.activity._recent_prompts",
            return_value=[],
        ):
            result = svc.get_activity()
        assert "sessions" in result
        assert "recent" in result

    def test_serializes_sessions(self):
        session = ActiveSession(
            cli="claude", session_id="", project="myapp",
            project_path="/Users/me/myapp", status="running",
            last_prompt="fix bug", agent_name="", team_name="",
            pid=1234,
        )
        svc = ActivityService()
        with patch(
            "maggy.services.activity._scan_processes",
            return_value=[session],
        ), patch(
            "maggy.services.activity._recent_prompts",
            return_value=[],
        ):
            result = svc.get_activity()
        assert len(result["sessions"]) == 1
        s = result["sessions"][0]
        assert s["cli"] == "claude"
        assert s["project"] == "myapp"
        assert s["pid"] == 1234

    def test_serializes_prompts(self):
        prompt = RecentPrompt(
            cli="codex", text="deploy",
            project="api", timestamp="2026-05-10T12:00:00",
            session_id="c1",
        )
        svc = ActivityService()
        with patch(
            "maggy.services.activity._scan_processes",
            return_value=[],
        ), patch(
            "maggy.services.activity._recent_prompts",
            return_value=[prompt],
        ):
            result = svc.get_activity()
        assert len(result["recent"]) == 1
        assert result["recent"][0]["text"] == "deploy"
