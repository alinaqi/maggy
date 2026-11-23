"""`maggy harness init`: detect agents, write the profile, mint AWG tokens."""

from __future__ import annotations

import os
import pwd
import stat
from pathlib import Path

import yaml
from harness_cli_helpers import TESTED, FakeTools, invoke, make_env

REAL_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)


def _two_agents(initialised: bool = False) -> FakeTools:
    return FakeTools({"claude": TESTED["claude"], "pi": TESTED["pi"]}, awg={"initialised": initialised})


def test_init_yes_writes_profile_and_private_tokens(tmp_path: Path) -> None:
    before = sorted(p.name for p in (REAL_HOME / ".maggy").glob("*")) if (REAL_HOME / ".maggy").is_dir() else []
    tools = _two_agents()
    env = make_env(tmp_path, tools)
    result = invoke(env, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    profile = yaml.safe_load((env.home / ".maggy" / "harness.yaml").read_text())
    assert profile["agents"] == {"installed": ["claude", "pi"], "default": "claude"}
    assert profile["work"]["provider"] == "awg"
    for agent in ("claude", "pi"):
        token = env.home / ".maggy" / "tokens" / f"{agent}.token"
        assert token.read_text() == f"SECRET-maggy-{agent}"
        assert stat.S_IMODE(token.stat().st_mode) == 0o600
    assert "SECRET" not in result.output
    after = sorted(p.name for p in (REAL_HOME / ".maggy").glob("*")) if (REAL_HOME / ".maggy").is_dir() else []
    assert before == after


def test_init_runs_awg_init_and_mints_with_argv_lists(tmp_path: Path) -> None:
    tools = _two_agents()
    invoke(make_env(tmp_path, tools), ["init", "--yes"])
    assert ["awg", "init"] in tools.calls
    assert ["awg", "token", "mint", "maggy-claude", "--kind", "agent", "--json"] in tools.calls
    assert ["claude", "--version"] in tools.calls


def test_init_skips_awg_init_when_initialised_and_keeps_tokens(tmp_path: Path) -> None:
    tools = _two_agents(initialised=True)
    env = make_env(tmp_path, tools)
    invoke(env, ["init", "--yes"])
    tools.calls.clear()
    result = invoke(env, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    assert ["awg", "init"] not in tools.calls
    assert not [c for c in tools.calls if c[1:3] == ["token", "mint"]]


def test_init_without_awg_still_writes_profile(tmp_path: Path) -> None:
    tools = FakeTools({"codex": TESTED["codex"]})
    env = make_env(tmp_path, tools)
    result = invoke(env, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    assert "awg not found" in result.output
    assert (env.home / ".maggy" / "harness.yaml").is_file()
    assert not (env.home / ".maggy" / "tokens").exists()


def test_init_interview_answers_shape_the_profile(tmp_path: Path) -> None:
    tools = _two_agents()
    env = make_env(tmp_path, tools)
    result = invoke(env, ["init"], text="cursor\npi\nquality\nn\ny\n")
    assert result.exit_code == 0, result.output
    profile = yaml.safe_load((env.home / ".maggy" / "harness.yaml").read_text())
    assert profile["agents"]["default"] == "pi"
    assert profile["models"]["strategy"] == "quality"
    assert profile["work"]["provider"] == "none"
    assert profile["surfaces"] == ["t3"]
    assert not [c for c in tools.calls if c[0] == "awg"]


def test_init_keeps_an_existing_profile_without_force(tmp_path: Path) -> None:
    env = make_env(tmp_path, _two_agents())
    path = env.home / ".maggy" / "harness.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("version: 1\nskills: [python]\n")
    result = invoke(env, ["init", "--yes"])
    assert result.exit_code == 0, result.output
    assert "skills: [python]" in path.read_text()
    assert "kept" in result.output


def test_init_mint_failure_exits_one_without_token(tmp_path: Path) -> None:
    tools = FakeTools({"claude": TESTED["claude"]}, awg={"initialised": True, "mint_fails": True})
    env = make_env(tmp_path, tools)
    result = invoke(env, ["init", "--yes"])
    assert result.exit_code == 1
    assert "claude: awg token mint failed" in result.output
    assert not (env.home / ".maggy" / "tokens" / "claude.token").exists()
