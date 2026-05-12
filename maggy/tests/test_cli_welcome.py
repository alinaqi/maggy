"""Tests for the CLI welcome banner."""

from __future__ import annotations

from unittest.mock import MagicMock

from maggy.cli_welcome import render_welcome


def _mock_client():
    return MagicMock()


SESSION = {
    "id": "abc123",
    "project_key": "edubites",
    "working_dir": "/tmp/edubites",
    "status": "idle",
    "messages": 5,
}


def test_render_welcome_shows_project(capsys):
    render_welcome("edubites", SESSION, _mock_client())
    out = capsys.readouterr().out
    assert "edubites" in out


def test_render_welcome_shows_path(capsys):
    render_welcome("edubites", SESSION, _mock_client())
    out = capsys.readouterr().out
    assert "/tmp/edubites" in out


def test_render_welcome_shows_resuming(capsys):
    """Shows 'Resuming' when session has messages."""
    render_welcome("edubites", SESSION, _mock_client())
    out = capsys.readouterr().out
    assert "Resuming" in out
    assert "5 msgs" in out


def test_render_welcome_new_session(capsys):
    """New session (0 msgs) does not show Resuming."""
    session = {**SESSION, "messages": 0}
    render_welcome("edubites", session, _mock_client())
    out = capsys.readouterr().out
    assert "Resuming" not in out


def test_render_welcome_shows_help_hint(capsys):
    render_welcome("edubites", SESSION, _mock_client())
    out = capsys.readouterr().out
    assert "/help" in out


def test_dir_shows_cwd_fallback(capsys):
    """Uses os.getcwd() when working_dir missing."""
    import os
    session = {**SESSION, "working_dir": ""}
    render_welcome("edubites", session, _mock_client())
    out = capsys.readouterr().out
    cwd_tail = os.path.basename(os.getcwd())
    assert cwd_tail in out
