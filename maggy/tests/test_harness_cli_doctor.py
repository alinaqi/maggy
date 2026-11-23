"""`maggy harness doctor`: capabilities, version drift, tokens, AWG, T3 advice."""

from __future__ import annotations

import subprocess
from pathlib import Path

from harness_cli_helpers import TESTED, FakeTools, invoke, make_env, write_profile, write_tokens

from maggy.harness.cli.detect import agent_version

AGENTS = ["claude", "codex", "opencode", "pi"]


def _setup(tmp_path: Path, versions: dict, awg: dict | None = None):
    tools = FakeTools(versions, awg=awg if awg is not None else {"initialised": True})
    env = make_env(tmp_path, tools)
    write_profile(env, {"agents": {"installed": AGENTS}, "surfaces": []})
    return tools, env


def test_doctor_all_good_exits_zero_with_capability_table(tmp_path: Path) -> None:
    tools, env = _setup(tmp_path, dict(TESTED))
    write_tokens(env, AGENTS)
    result = invoke(env, ["doctor"])
    assert result.exit_code == 0, result.output
    lines = {line.split()[0]: line for line in result.output.splitlines() if line.strip()}
    assert "native" in lines["claude"] and "partial" in lines["claude"]
    assert "none" in lines["codex"]
    assert "drift" not in result.output


def test_doctor_warns_on_version_drift_and_missing_agent(tmp_path: Path) -> None:
    versions = {**TESTED, "opencode": "1.20.0"}
    del versions["pi"]
    _, env = _setup(tmp_path, versions)
    write_tokens(env, AGENTS)
    result = invoke(env, ["doctor"])
    assert "opencode 1.20.0 drifts from tested 1.19.6" in result.output
    assert "pi: not found on PATH" in result.output
    assert result.exit_code == 1


def test_doctor_reports_missing_tokens(tmp_path: Path) -> None:
    _, env = _setup(tmp_path, dict(TESTED))
    write_tokens(env, ["claude", "codex", "opencode"])
    result = invoke(env, ["doctor"])
    assert result.exit_code == 1
    assert f"missing token file {env.home / '.maggy' / 'tokens' / 'pi.token'}" in result.output


def test_doctor_checks_awg_reachability_per_token(tmp_path: Path) -> None:
    tools, env = _setup(tmp_path, dict(TESTED), awg={"initialised": True, "unreachable": ["codex.token"]})
    write_tokens(env, AGENTS)
    result = invoke(env, ["doctor"])
    token = str(env.home / ".maggy" / "tokens" / "claude.token")
    assert ["awg", "--token-file", token, "status"] in tools.calls
    assert "codex: AWG not reachable with" in result.output
    assert "claude: AWG reachable" in result.output
    assert result.exit_code == 1


def test_doctor_gives_t3_advice_only_with_t3_surface(tmp_path: Path) -> None:
    _, env = _setup(tmp_path, dict(TESTED))
    write_tokens(env, AGENTS)
    assert "T3" not in invoke(env, ["doctor"]).output
    write_profile(env, {"agents": {"installed": AGENTS}, "surfaces": ["t3"]})
    output = invoke(env, ["doctor"]).output
    assert "T3 inherits" in output
    assert "--scope project" in output


def test_agent_version_reads_stderr_too(tmp_path: Path) -> None:
    """pi prints its version on stderr."""
    env = make_env(tmp_path, FakeTools({"pi": "0.73.1"}))
    env.run = lambda argv: subprocess.CompletedProcess(argv, 0, "", "0.73.1\n")
    assert agent_version(env, "pi") == "0.73.1"
