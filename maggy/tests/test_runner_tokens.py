"""Runner credentials: `harness init` mints runner-agent (agent) + runner-ci (ci); doctor checks both."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from harness_cli_helpers import TESTED, FakeTools, invoke, make_env, write_profile, write_tokens

from maggy.runner.cli_setup import runner_token_files
from maggy.worker.launch import Refused

RUNNER = {"runner-agent": "agent", "runner-ci": "ci"}


def _tools(initialised: bool = False) -> FakeTools:
    return FakeTools({"claude": TESTED["claude"]}, awg={"initialised": initialised})


def test_init_mints_runner_agent_and_ci_tokens_private(tmp_path: Path) -> None:
    tools = _tools()
    env = make_env(tmp_path, tools)
    result = invoke(env, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    for name, kind in RUNNER.items():
        assert ["awg", "token", "mint", f"maggy-{name}", "--kind", kind, "--json"] in tools.calls
        token = env.home / ".maggy" / "tokens" / f"{name}.token"
        assert token.read_text() == f"SECRET-maggy-{name}"
        assert stat.S_IMODE(token.stat().st_mode) == 0o600
    assert "SECRET" not in result.output


def test_init_keeps_existing_runner_tokens(tmp_path: Path) -> None:
    tools = _tools()
    env = make_env(tmp_path, tools)
    invoke(env, ["init", "--yes"])
    tools.calls.clear()
    assert invoke(env, ["init", "--yes"]).exit_code == 0
    assert not [c for c in tools.calls if c[1:3] == ["token", "mint"]]


def _doctor_env(tmp_path: Path, awg: dict | None = None):
    tools = FakeTools(dict(TESTED), awg=awg or {"initialised": True})
    env = make_env(tmp_path, tools)
    write_profile(env, {"agents": {"installed": ["claude"]}, "surfaces": []})
    write_tokens(env, ["claude"])
    return tools, env


def test_doctor_checks_both_runner_tokens(tmp_path: Path) -> None:
    tools, env = _doctor_env(tmp_path)
    result = invoke(env, ["doctor"])
    assert result.exit_code == 0, result.output
    for name in RUNNER:
        token = str(env.home / ".maggy" / "tokens" / f"{name}.token")
        assert ["awg", "--token-file", token, "status"] in tools.calls
        assert f"{name}: AWG reachable" in result.output


def test_doctor_errors_on_missing_runner_ci_token(tmp_path: Path) -> None:
    _, env = _doctor_env(tmp_path)
    (env.home / ".maggy" / "tokens" / "runner-ci.token").unlink()
    result = invoke(env, ["doctor"])
    assert result.exit_code == 1
    assert "runner-ci: missing token file" in result.output


def test_doctor_errors_on_readable_runner_token(tmp_path: Path) -> None:
    _, env = _doctor_env(tmp_path)
    (env.home / ".maggy" / "tokens" / "runner-agent.token").chmod(0o644)
    result = invoke(env, ["doctor"])
    assert result.exit_code == 1
    assert "runner-agent: token file" in result.output and "0600" in result.output


def test_runner_reads_tokens_from_the_tokens_dir(tmp_path: Path) -> None:
    tokens = tmp_path / "tokens"
    tokens.mkdir()
    for name in RUNNER:
        (tokens / f"{name}.token").write_text("x")
    assert runner_token_files(tmp_path) == (tokens / "runner-agent.token",
                                            tokens / "runner-ci.token")


def test_runner_refuses_without_tokens_naming_the_files(tmp_path: Path) -> None:
    with pytest.raises(Refused, match="runner-ci.token"):
        runner_token_files(tmp_path)
