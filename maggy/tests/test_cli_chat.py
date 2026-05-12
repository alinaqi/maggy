"""Tests for maggy chat CLI — interactive REPL."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from maggy.cli import app
from maggy.cli_chat import cwd_project

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


def _setup_resumed(mock_client, working_dir="/tmp/my-proj"):
    """Configure mocks for session resume by working_dir."""
    mock_client.ensure_server.return_value = True
    mock_client.chat_sessions.return_value = [
        {**RESUMED, "working_dir": working_dir},
    ]
    mock_client.chat_history.return_value = HISTORY
    mock_client.budget_summary.return_value = {
        "spent_today_usd": 0, "daily_limit_usd": 10, "status": "ok",
    }
    mock_client.models_heatmap.return_value = []


# -- cwd_project tests --


def test_cwd_project_returns_name_and_path(tmp_path, monkeypatch):
    """cwd_project returns (folder_name, resolved_path)."""
    monkeypatch.chdir(tmp_path)
    name, path = cwd_project()
    assert name == tmp_path.name
    assert path == str(tmp_path.resolve())


def test_cwd_project_resolves_symlinks(tmp_path, monkeypatch):
    """cwd_project resolves symlinks."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    monkeypatch.chdir(link)
    name, path = cwd_project()
    assert name == "real"
    assert path == str(real.resolve())


# -- chat command tests --


@patch("maggy.cli._client")
def test_chat_creates_session(mock_client, tmp_path, monkeypatch):
    """Creates new session when none match working_dir."""
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/quit"]
        result = runner.invoke(app, ["chat"])
    assert result.exit_code == 0
    mock_client.chat_create.assert_called_once_with(
        tmp_path.name, str(tmp_path.resolve()),
    )


@patch("maggy.cli._client")
def test_chat_resumes_by_working_dir(mock_client, tmp_path, monkeypatch):
    """Resumes session matched by working_dir path."""
    monkeypatch.chdir(tmp_path)
    wd = str(tmp_path.resolve())
    _setup_resumed(mock_client, working_dir=wd)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/quit"]
        result = runner.invoke(app, ["chat"])
    assert result.exit_code == 0
    assert "Resuming" in result.output
    mock_client.chat_create.assert_not_called()


@patch("maggy.cli._client")
def test_chat_explicit_project_arg(mock_client, tmp_path, monkeypatch):
    """Explicit project arg is used as project name."""
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/quit"]
        result = runner.invoke(app, ["chat", "my-proj"])
    assert result.exit_code == 0
    mock_client.chat_create.assert_called_once_with(
        "my-proj", str(tmp_path.resolve()),
    )


@patch("maggy.cli._client")
def test_chat_routed_streams(mock_client, tmp_path, monkeypatch):
    """Routed chat sends via send_routed and shows model."""
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    mock_client.chat_send_routed.return_value = iter([
        {"type": "routing", "model": "kimi", "blast": 3,
         "reason": "low blast"},
        {"type": "text", "content": "Hello"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["say hi", "/quit"]
        result = runner.invoke(app, ["chat"])
    assert result.exit_code == 0
    mock_client.chat_send_routed.assert_called_once_with(
        "abc123", "say hi", blast=None, allowed_models=None,
    )


@patch("maggy.cli._client")
def test_chat_direct_mode(mock_client, tmp_path, monkeypatch):
    """--direct flag uses send_stream instead of routed."""
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    mock_client.chat_send_stream.return_value = iter([
        {"type": "text", "content": "Hi"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["say hi", "/quit"]
        result = runner.invoke(app, ["chat", "--direct"])
    assert result.exit_code == 0
    mock_client.chat_send_stream.assert_called_once_with(
        "abc123", "say hi",
    )


@patch("maggy.cli._client")
def test_chat_history_command(mock_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    mock_client.chat_history.return_value = HISTORY
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/history", "/quit"]
        result = runner.invoke(app, ["chat"])
    assert result.exit_code == 0


@patch("maggy.cli._client")
def test_chat_blast_override(mock_client, tmp_path, monkeypatch):
    """'/blast 8' sets override for next message."""
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    mock_client.chat_send_routed.return_value = iter([
        {"type": "routing", "model": "claude", "blast": 8,
         "reason": "override"},
        {"type": "text", "content": "Done"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/blast 8", "do it", "/quit"]
        result = runner.invoke(app, ["chat"])
    assert result.exit_code == 0
    mock_client.chat_send_routed.assert_called_once_with(
        "abc123", "do it", blast=8, allowed_models=None,
    )


@patch("maggy.cli._client")
def test_chat_ctrl_c_exits(mock_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = KeyboardInterrupt
        result = runner.invoke(app, ["chat"])
    assert result.exit_code == 0


@patch("maggy.cli._client")
def test_chat_empty_input_ignored(mock_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["", "  ", "/quit"]
        result = runner.invoke(app, ["chat"])
    assert result.exit_code == 0
    mock_client.chat_send_routed.assert_not_called()


@patch("maggy.cli._client")
def test_chat_error_displayed(mock_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    mock_client.chat_send_routed.return_value = iter([
        {"type": "error", "content": "CLI not found"},
        {"type": "done"},
    ])
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["test", "/quit"]
        result = runner.invoke(app, ["chat"])
    assert result.exit_code == 0


@patch("maggy.cli._client")
def test_chat_exit_word_quits(mock_client, tmp_path, monkeypatch):
    """Typing 'exit' terminates the REPL."""
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["exit"]
        result = runner.invoke(app, ["chat"])
    assert result.exit_code == 0
    mock_client.chat_send_routed.assert_not_called()


@patch("maggy.cli._client")
def test_chat_prompt_uses_angle_bracket(mock_client, tmp_path, monkeypatch):
    """Prompt uses '>' character."""
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/quit"]
        runner.invoke(app, ["chat"])
    call_args = mp.ask.call_args[0][0]
    assert ">" in call_args


@patch("maggy.cli._client")
def test_screenshot_command_dispatches(mock_client, tmp_path, monkeypatch):
    """'/screenshot path.png' calls vision handler."""
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp, \
         patch("maggy.cli_chat._handle_screenshot") as mh:
        mp.ask.side_effect = ["/screenshot test.png", "/quit"]
        runner.invoke(app, ["chat"])
    mh.assert_called_once()
    assert "test.png" in mh.call_args[0][0]


# -- main callback tests --


@patch("maggy.cli._client")
def test_main_always_enters_repl(mock_client, tmp_path, monkeypatch):
    """Running 'maggy' with no args enters REPL for cwd."""
    monkeypatch.chdir(tmp_path)
    _setup_new(mock_client)
    with patch("maggy.cli_chat.Prompt") as mp:
        mp.ask.side_effect = ["/quit"]
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert tmp_path.name in result.output
