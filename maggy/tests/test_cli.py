"""Tests for Maggy CLI — thin client over REST API."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from maggy.cli import app

runner = CliRunner()


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _mock_server_running(monkeypatch):
    """Pretend server is always up."""
    monkeypatch.setattr(
        "maggy.cli_client.MaggyClient._check_health",
        lambda self: True,
    )


def _mock_get(response_json: dict | list):
    """Return a mock httpx response."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = response_json
    resp.raise_for_status = MagicMock()
    return resp


# ── Status ──────────────────────────────────────────────────────────


def test_status_shows_health():
    health = {
        "status": "ok",
        "mode": "full",
        "org": "Protaige",
        "codebases": 5,
        "provider": "github",
    }
    with patch("maggy.cli_client.httpx.get", return_value=_mock_get(health)):
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "Protaige" in result.output


def test_status_json_flag():
    health = {"status": "ok", "mode": "full", "org": "X", "codebases": 1}
    with patch("maggy.cli_client.httpx.get", return_value=_mock_get(health)):
        result = runner.invoke(app, ["status", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["status"] == "ok"


# ── Inbox ───────────────────────────────────────────────────────────


def test_inbox_renders_table():
    items = {
        "items": [
            {"rank": 1, "title": "Fix auth bug", "labels": ["bug"], "ai_reason": "critical", "id": "1", "board": "repo"},
            {"rank": 2, "title": "Add tests", "labels": ["test"], "ai_reason": "coverage", "id": "2", "board": "repo"},
        ],
        "total": 2,
    }
    with patch("maggy.cli_client.httpx.get", return_value=_mock_get(items)):
        result = runner.invoke(app, ["inbox"])
    assert result.exit_code == 0
    assert "Fix auth bug" in result.output


def test_inbox_empty():
    with patch("maggy.cli_client.httpx.get", return_value=_mock_get({"items": [], "total": 0})):
        result = runner.invoke(app, ["inbox"])
    assert result.exit_code == 0
    assert "No tasks" in result.output


# ── Sessions ────────────────────────────────────────────────────────


def test_sessions_renders():
    data = {
        "sessions": [
            {"pid": 1234, "tool": "claude", "project": "myapp", "prompts": 42, "duration": "1h 20m"},
        ],
        "total": 1,
    }
    with patch("maggy.cli_client.httpx.get", return_value=_mock_get(data)):
        result = runner.invoke(app, ["sessions"])
    assert result.exit_code == 0
    assert "claude" in result.output


# ── Route ───────────────────────────────────────────────────────────


def test_route_decision():
    decision = {
        "primary": "claude",
        "validator": "codex",
        "fallback": ["kimi", "ollama"],
        "reason": "blast 8 → premium tier",
    }
    with patch("maggy.cli_client.httpx.get", return_value=_mock_get(decision)):
        result = runner.invoke(app, ["route", "8"])
    assert result.exit_code == 0
    assert "claude" in result.output


# ── Budget ──────────────────────────────────────────────────────────


def test_budget_renders():
    data = {
        "daily_limit_usd": 10.0,
        "used_today_usd": 3.50,
        "providers": [
            {"name": "anthropic", "used": 2.50, "limit": 5.0},
            {"name": "openai", "used": 1.00, "limit": 3.0},
        ],
    }
    with patch("maggy.cli_client.httpx.get", return_value=_mock_get(data)):
        result = runner.invoke(app, ["budget"])
    assert result.exit_code == 0
    assert "anthropic" in result.output


# ── Competitors ─────────────────────────────────────────────────────


def test_competitors_news():
    news = [
        {"date": "2026-05-11", "source": "TechCrunch", "event_type": "funding", "headline": "Rival raises $50M"},
    ]
    with patch("maggy.cli_client.httpx.get", return_value=_mock_get(news)):
        result = runner.invoke(app, ["competitors"])
    assert result.exit_code == 0
    assert "Rival" in result.output


# ── Models ──────────────────────────────────────────────────────────


def test_models_heatmap():
    heatmap = [
        {"model": "claude", "task_type": "security", "reward": 0.92},
        {"model": "codex", "task_type": "crud", "reward": 0.85},
    ]
    with patch("maggy.cli_client.httpx.get", return_value=_mock_get(heatmap)):
        result = runner.invoke(app, ["models"])
    assert result.exit_code == 0
    assert "claude" in result.output


# ── Server auto-start ───────────────────────────────────────────────


def test_server_not_running_starts_it(monkeypatch):
    """If health check fails, CLI should attempt to start server."""
    monkeypatch.undo()  # remove autouse mock
    call_count = {"n": 0}

    def fake_check(self):
        call_count["n"] += 1
        if call_count["n"] <= 1:
            return False
        return True

    monkeypatch.setattr(
        "maggy.cli_client.MaggyClient._check_health",
        fake_check,
    )
    monkeypatch.setattr(
        "maggy.cli_client.MaggyClient._start_server",
        lambda self: None,
    )
    health = {"status": "ok", "mode": "local", "org": "Test", "codebases": 0}
    with patch("maggy.cli_client.httpx.get", return_value=_mock_get(health)):
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_stale_port_killed_before_start(monkeypatch):
    """Stale port holder is killed before spawning server."""
    monkeypatch.undo()
    calls = {"health": 0, "kill": 0}

    def fake_check(self):
        calls["health"] += 1
        return calls["health"] > 2

    monkeypatch.setattr(
        "maggy.cli_client.MaggyClient._check_health",
        fake_check,
    )
    monkeypatch.setattr(
        "maggy.cli_client.MaggyClient._start_server",
        lambda self: None,
    )
    monkeypatch.setattr(
        "maggy.cli_client.MaggyClient._kill_stale_port",
        lambda self: calls.__setitem__("kill", 1),
    )
    health = {
        "status": "ok", "mode": "local",
        "org": "T", "codebases": 0,
    }
    with patch(
        "maggy.cli_client.httpx.get",
        return_value=_mock_get(health),
    ):
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert calls["kill"] == 1


def test_server_log_written_to_file(monkeypatch, tmp_path):
    """Server stdout/stderr go to ~/.maggy/server.log."""
    monkeypatch.setattr("maggy.cli_client.CONFIG_DIR", tmp_path)
    captured = {}

    def fake_popen(cmd, **kw):
        captured.update(kw)

    monkeypatch.setattr(
        "maggy.cli_client.subprocess.Popen", fake_popen,
    )
    from maggy.cli_client import MaggyClient
    MaggyClient()._start_server()
    assert captured.get("stdout") is not subprocess.DEVNULL
    assert (tmp_path / "server.log").exists()
