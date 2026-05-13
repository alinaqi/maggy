"""Tests for REPL slash command handlers."""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import MagicMock

from maggy.cli_repl_cmds import (
    cmd_budget,
    cmd_help,
    cmd_models,
    cmd_route,
    cmd_stats,
    cmd_use,
    dispatch,
)
from maggy.cli_repl_info import (
    cmd_claude_md,
    cmd_health,
    cmd_thinking,
)


@dataclass
class FakeState:
    working_dir: str = "/tmp/proj"
    session_id: str = "s1"
    allowed_models: list[str] = field(default_factory=list)
    last_tool_events: list[str] = field(default_factory=list)


def _mock_client():
    c = MagicMock()
    c.budget_summary.return_value = {
        "spent_today_usd": 1.5,
        "daily_limit_usd": 10.0,
        "status": "ok",
        "input_tokens": 12500,
        "output_tokens": 3400,
    }
    c.budget_by_provider.return_value = [
        {"provider": "anthropic", "spent_usd": 1.2},
        {"provider": "openai", "spent_usd": 0.3},
    ]
    c.models_heatmap.return_value = [
        {"model": "claude", "task_type": "security",
         "avg_reward": 0.95, "samples": 10},
    ]
    c.routing_rules.return_value = {
        "mode": "dynamic",
        "task_type_overrides": {
            "security": {"model": "claude", "reason": "deep"},
        },
        "model_performance": {
            "claude": {"success_rate": 1.0, "strengths": ["security"]},
        },
    }
    c.config.return_value = {
        "codebases": [{"key": "proj", "path": "/tmp/proj"}],
        "routing": {"mode": "dynamic"},
        "budget": {"daily_limit_usd": 10.0},
    }
    return c


def test_dispatch_stats(capsys):
    """'/stats' dispatches to stats handler."""
    client = _mock_client()
    state = FakeState()
    handled = dispatch("/stats", client, state)
    assert handled is True


def test_dispatch_unknown():
    """Unknown commands return False."""
    handled = dispatch("/xyz123", MagicMock(), FakeState())
    assert handled is False


def test_cmd_stats(capsys):
    """Stats shows budget and model perf."""
    cmd_stats(_mock_client())
    out = capsys.readouterr().out
    assert "1.5" in out or "budget" in out.lower()


def test_cmd_budget(capsys):
    """Budget shows per-provider breakdown."""
    cmd_budget(_mock_client())
    out = capsys.readouterr().out
    assert "anthropic" in out or "1.2" in out


def test_cmd_route(capsys):
    """Route shows task type overrides."""
    cmd_route(_mock_client())
    out = capsys.readouterr().out
    assert "security" in out or "claude" in out


def test_cmd_models(capsys):
    """Models shows reward heatmap."""
    cmd_models(_mock_client())
    out = capsys.readouterr().out
    assert "claude" in out or "0.95" in out


def test_cmd_use_sets_models():
    """'/use claude,codex' sets allowed_models."""
    state = FakeState()
    cmd_use("claude,codex", state)
    assert state.allowed_models == ["claude", "codex"]


def test_cmd_use_reset():
    """'/use all' clears allowed_models."""
    state = FakeState(allowed_models=["claude"])
    cmd_use("all", state)
    assert state.allowed_models == []


def test_cmd_claude_md_missing(capsys):
    """Shows message when CLAUDE.md not found."""
    state = FakeState(working_dir="/nonexistent_xyz_dir")
    cmd_claude_md(state)
    out = capsys.readouterr().out
    assert "not found" in out.lower() or "no" in out.lower()


def test_cmd_stats_shows_tokens(capsys):
    """Stats displays token counts when available."""
    cmd_stats(_mock_client())
    out = capsys.readouterr().out
    assert "12,500" in out
    assert "3,400" in out


def test_cmd_route_shows_tiers(capsys):
    """Route displays blast tier reference."""
    cmd_route(_mock_client())
    out = capsys.readouterr().out
    assert "cheap" in out.lower()
    assert "premium" in out.lower()


def test_cmd_help(capsys):
    """Help lists all commands."""
    cmd_help()
    out = capsys.readouterr().out
    assert "/stats" in out
    assert "/use" in out
    assert "/help" in out


def test_cmd_health(capsys):
    """Health shows engram and mnemos status."""
    from maggy.cli_repl_info import cmd_health
    client = _mock_client()
    client.health_dashboard.return_value = {
        "engram": {"health_score": 0.85, "active": 42, "total": 50},
        "mnemos": {"state": "ok", "composite": 0.3},
    }
    cmd_health(client)
    out = capsys.readouterr().out
    assert "85%" in out or "0.85" in out
    assert "ok" in out.lower()


def test_dispatch_health(capsys):
    """/health dispatches to health handler."""
    client = _mock_client()
    client.health_dashboard.return_value = {
        "engram": {"health_score": 0.9, "active": 10, "total": 12},
        "mnemos": {"state": "ok", "composite": 0.2},
    }
    state = FakeState()
    handled = dispatch("/health", client, state)
    assert handled is True


def test_help_lists_health(capsys):
    """/help mentions /health command."""
    cmd_help()
    out = capsys.readouterr().out
    assert "/health" in out


def test_models_empty_shows_known(capsys):
    """Empty heatmap shows known model names."""
    from maggy.cli_repl_cmds import cmd_models
    client = _mock_client()
    client.models_heatmap.return_value = []
    cmd_models(client)
    out = capsys.readouterr().out
    assert "local" in out
    assert "claude" in out


def test_use_warns_unknown_model(capsys):
    """/use with unknown model name prints warning."""
    state = FakeState()
    cmd_use("badmodel,claude", state)
    out = capsys.readouterr().out
    assert "unknown" in out.lower() or "Unknown" in out


def test_budget_subscription_plan(capsys):
    """Subscription plan shows 'Subscription' instead of dollar amounts."""
    client = _mock_client()
    client.budget_summary.return_value = {
        "spent_today_usd": 0, "daily_limit_usd": 10.0,
        "status": "ok", "plan": "subscription",
    }
    client.budget_by_provider.return_value = []
    cmd_budget(client)
    out = capsys.readouterr().out
    assert "subscription" in out.lower()


def test_health_graceful_failure(capsys):
    """Health command handles server failure gracefully."""
    from maggy.cli_repl_info import cmd_health
    client = _mock_client()
    client.health_dashboard.side_effect = Exception("unreachable")
    cmd_health(client)
    out = capsys.readouterr().out
    assert "health" in out.lower() or out == ""


def test_stats_server_down(capsys):
    """Stats handles server failure gracefully."""
    client = _mock_client()
    client.budget_summary.side_effect = Exception("unreachable")
    cmd_stats(client)
    # Should not crash — may show empty or partial data


def test_dispatch_thinking():
    """/thinking dispatches to thinking handler."""
    state = FakeState()
    state.last_tool_events = ["Read main.py", "$ git status"]
    handled = dispatch("/thinking", _mock_client(), state)
    assert handled is True


def test_thinking_shows_events(capsys):
    """cmd_thinking prints stored tool events."""
    from maggy.cli_repl_info import cmd_thinking
    from maggy.cli_repl_cmds import SessionState
    state = SessionState(
        session_id="s1", working_dir="/tmp",
    )
    state.last_tool_events = [
        "Read src/main.py",
        "$ git status",
        "Grep TODO",
    ]
    cmd_thinking(state)
    out = capsys.readouterr().out
    assert "Read" in out
    assert "git status" in out
    assert "Grep" in out


def test_thinking_empty(capsys):
    """cmd_thinking shows message when no events."""
    from maggy.cli_repl_info import cmd_thinking
    from maggy.cli_repl_cmds import SessionState
    state = SessionState(
        session_id="s1", working_dir="/tmp",
    )
    state.last_tool_events = []
    cmd_thinking(state)
    out = capsys.readouterr().out
    assert "no tool" in out.lower()


def test_help_lists_thinking(capsys):
    """/help mentions /thinking command."""
    cmd_help()
    out = capsys.readouterr().out
    assert "/thinking" in out
