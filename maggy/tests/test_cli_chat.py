"""Tests for maggy chat CLI — interactive REPL."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from maggy.cli import app

runner = CliRunner()

SESSION = {
    "id": "abc123",
    "project_key": "my-proj",
    "working_dir": "/tmp/my-proj",
    "status": "idle",
    "messages": 0,
}

RESUMED = {
    "id": "abc123",
    "project_key": "my-proj",
    "working_dir": "/tmp/my-proj",
    "status": "idle",
    "messages": 5,
}

HISTORY = {
    "id": "abc123",
    "messages": [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ],
}


@pytest.fixture(autouse=True)
def _no_detect(monkeypatch):
    """Prevent real CLI detection in tests."""
    from maggy.services import session_detect
    monkeypatch.setattr(
        session_detect, "detect_all",
        lambda wd: session_detect.DetectedSessions(),
    )


def _setup_new(mock_client):
    """Configure client mocks for new session flow."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_sessions.return_value = []
    mock_client.chat_create.return_value = SESSION
    mock_client.chat_history.return_value = {"messages": []}
    mock_client.budget_summary.return_value = {
        "spent_today_usd": 0, "daily_limit_usd": 10, "status": "ok",
    }
    mock_client.models_heatmap.return_value = []


@patch("maggy.cli._client")
def test_chat_creates_session(mock_client):
    """Creates new session when none exist for project."""
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    assert "my-proj" in result.output
    mock_client.chat_create.assert_called_once_with("my-proj")


@patch("maggy.cli._client")
def test_chat_resumes_existing(mock_client):
    """Resumes existing session instead of creating new."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_sessions.return_value = [RESUMED]
    mock_client.chat_history.return_value = HISTORY
    mock_client.budget_summary.return_value = {
        "spent_today_usd": 0, "daily_limit_usd": 10, "status": "ok",
    }
    mock_client.models_heatmap.return_value = []
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    assert "Resuming" in result.output
    mock_client.chat_create.assert_not_called()


@patch("maggy.cli._client")
def test_chat_routed_streams(mock_client):
    """Routed chat sends via send_routed and shows model."""
    _setup_new(mock_client)
    mock_client.chat_send_routed.return_value = iter([
        {"type": "routing", "model": "kimi", "blast": 3,
         "reason": "low blast"},
        {"type": "text", "content": "Hello"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["say hi", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_send_routed.assert_called_once_with(
        "abc123", "say hi", blast=None, allowed_models=None,
    )


@patch("maggy.cli._client")
def test_chat_direct_mode(mock_client):
    """--direct flag uses send_stream instead of routed."""
    _setup_new(mock_client)
    mock_client.chat_send_stream.return_value = iter([
        {"type": "text", "content": "Hi"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["say hi", "/quit"]
        result = runner.invoke(
            app, ["chat", "my-proj", "--direct"],
        )
    assert result.exit_code == 0
    mock_client.chat_send_stream.assert_called_once_with(
        "abc123", "say hi",
    )


@patch("maggy.cli._client")
def test_chat_history_command(mock_client):
    _setup_new(mock_client)
    mock_client.chat_history.return_value = HISTORY
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/history", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0


@patch("maggy.cli._client")
def test_chat_blast_override(mock_client):
    """'/blast 8' sets override for next message."""
    _setup_new(mock_client)
    mock_client.chat_send_routed.return_value = iter([
        {"type": "routing", "model": "claude", "blast": 8,
         "reason": "override"},
        {"type": "text", "content": "Done"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/blast 8", "do it", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_send_routed.assert_called_once_with(
        "abc123", "do it", blast=8, allowed_models=None,
    )


@patch("maggy.cli._client")
def test_chat_ctrl_c_exits(mock_client):
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = KeyboardInterrupt
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0


@patch("maggy.cli._client")
def test_chat_empty_input_ignored(mock_client):
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["", "  ", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_send_routed.assert_not_called()


@patch("maggy.cli._client")
def test_chat_error_displayed(mock_client):
    _setup_new(mock_client)
    mock_client.chat_send_routed.return_value = iter([
        {"type": "error", "content": "CLI not found"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["test", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0


@patch("maggy.cli._client")
def test_chat_shows_queued_status(mock_client):
    _setup_new(mock_client)
    mock_client.chat_send_routed.return_value = iter([
        {"type": "queued", "position": 2},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["test", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0


@patch("maggy.cli._client")
def test_chat_shows_warning(mock_client):
    _setup_new(mock_client)
    mock_client.chat_send_routed.return_value = iter([
        {"type": "warning", "content": "Context: ~25000 tokens"},
        {"type": "text", "content": "Hi"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["test", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0


@patch("maggy.cli._client")
def test_chat_exit_word_quits(mock_client):
    """Typing 'exit' terminates the REPL (not routed to LLM)."""
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["exit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_send_routed.assert_not_called()


@patch("maggy.cli._client")
def test_chat_agent_status_rendered(mock_client):
    """Agent status chunks render @model> step status."""
    _setup_new(mock_client)
    mock_client.chat_send_routed.return_value = iter([
        {"type": "agent_status", "agent": "local",
         "step": "ANALYZE", "status": "running"},
        {"type": "text", "content": "Done"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["test", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    assert "running" in result.output


@patch("maggy.cli._client")
def test_chat_quota_error_shows_guide(mock_client):
    """Quota error triggers account switch guidance."""
    _setup_new(mock_client)
    mock_client.chat_send_routed.return_value = iter([
        {"type": "error",
         "content": "rate_limit_exceeded: quota hit"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["test", "/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    out = result.output.lower()
    assert "switch" in out or "login" in out or "account" in out


@patch("maggy.cli._client")
def test_chat_prompt_uses_angle_bracket(mock_client):
    """Prompt uses '>' character, not 'maggy:'."""
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/quit"]
        runner.invoke(app, ["chat", "my-proj"])
    call_args = mp.ask.call_args[0][0]
    assert ">" in call_args
    assert "maggy" not in call_args.lower()


@patch("maggy.cli._client")
def test_screenshot_command_dispatches(mock_client):
    """'/screenshot path.png' calls vision handler."""
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp, \
         patch("maggy.cli_chat._handle_screenshot") as mh:
        mp.ask.side_effect = ["/screenshot test.png", "/quit"]
        runner.invoke(app, ["chat", "my-proj"])
    mh.assert_called_once()
    assert "test.png" in mh.call_args[0][0]
