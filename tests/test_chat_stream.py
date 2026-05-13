"""Tests for chat_stream build_cmd — session continuation."""
from __future__ import annotations

from types import SimpleNamespace

from maggy.services.chat_stream import build_cmd


def _session(claude_id: str = "", ctx: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        claude_session_id=claude_id,
        history_context=ctx,
    )


def test_resume_with_stored_id():
    s = _session(claude_id="abc-123")
    cmd = build_cmd(s, "hello")
    assert "--resume" in cmd
    assert "abc-123" in cmd
    assert "--continue" not in cmd


def test_continue_without_stored_id():
    s = _session()
    cmd = build_cmd(s, "hello")
    assert "--continue" in cmd
    assert "--resume" not in cmd


def test_continue_after_stale_clear():
    """After stale detection clears ID, retry uses --continue."""
    s = _session(claude_id="old-stale")
    cmd1 = build_cmd(s, "hello")
    assert "--resume" in cmd1

    s.claude_session_id = ""
    cmd2 = build_cmd(s, "hello")
    assert "--continue" in cmd2
    assert "--resume" not in cmd2


def test_prompt_in_cmd():
    s = _session()
    cmd = build_cmd(s, "fix the bug")
    assert "-p" in cmd
    idx = cmd.index("-p")
    assert cmd[idx + 1] == "fix the bug"


def test_history_context_prepended():
    s = _session(ctx="git: main branch")
    cmd = build_cmd(s, "what changed?")
    idx = cmd.index("-p")
    prompt = cmd[idx + 1]
    assert "[Context]" in prompt
    assert "git: main branch" in prompt
    assert s.history_context == ""
