"""Phase 1 exit (RFC personal-harness §3): on a clean HOME, `init` + `apply` give all four
agents the same rules, skills and AWG tools, and `doctor` reports every capability gap."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from harness_cli_helpers import TESTED, FakeTools, invoke
from harness_emitter_helpers import make_awg_repo
from harness_exit_helpers import (
    AGENTS, agent_dirs, awg_token_refs, codex_mcp_list, opencode_config, rules_block, skill_names,
)
from jsonschema import Draft202012Validator

from maggy.harness.cli import ToolEnv
from maggy.harness.compile import emitters_for
from maggy.harness.emitters import EmitterSources

MAGGY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = Path(__file__).parent / "fixtures" / "harness" / "opencode-1.19.6-config.schema.json"


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ToolEnv:
    """Temp HOME + temp repo (cwd), all four agents and awg faked; real Maggy sources."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    (tmp_path / "home").mkdir()
    (tmp_path / "repo").mkdir()
    monkeypatch.chdir(tmp_path / "repo")
    sources = EmitterSources(root=MAGGY_ROOT, awg_repo=make_awg_repo(tmp_path))
    tools = FakeTools(dict(TESTED), awg={"initialised": False})
    made = ToolEnv(run=tools.run, which=tools.which, home=tmp_path / "home", sources=sources)
    for args in (["init", "--yes", "--preset", "token-economy"], ["apply", "--yes"]):
        result = invoke(made, args)
        assert result.exit_code == 0, result.output
    return made


def test_every_agent_gets_the_identical_rules_block(env: ToolEnv) -> None:
    dirs = agent_dirs(env.home)
    blocks = {agent: rules_block(dirs[agent] / "AGENTS.md") for agent in AGENTS}
    assert len(set(blocks.values())) == 1, blocks
    assert "| Tier | Model |" in blocks["codex"]
    assert "@AGENTS.md" in (dirs["claude"] / "CLAUDE.md").read_text()
    assert str(dirs["opencode"] / "AGENTS.md") in opencode_config(env.home)["instructions"]


def test_every_agent_gets_the_same_skills(env: ToolEnv) -> None:
    found = {agent: skill_names(env.home, agent) for agent in AGENTS}
    assert found == {agent: {"model-routing", "awg"} for agent in AGENTS}


def test_every_agent_is_wired_to_awg_with_its_own_token(env: ToolEnv) -> None:
    tokens = env.home / ".maggy" / "tokens"
    assert awg_token_refs(env.home) == {agent: str(tokens / f"{agent}.token") for agent in AGENTS}
    for agent in AGENTS:
        assert (tokens / f"{agent}.token").read_text() == f"SECRET-maggy-{agent}"
    assert (agent_dirs(env.home)["pi"] / "extensions" / "awg" / "index.ts").is_file()


def test_second_apply_is_a_noop(env: ToolEnv) -> None:
    lock = env.home / ".maggy" / "harness.lock"
    before = lock.read_text()
    result = invoke(env, ["apply", "--yes"])
    assert result.exit_code == 0, result.output
    assert "Nothing to apply" in result.output
    assert lock.read_text() == before


def test_doctor_exits_zero_and_lists_every_capability_gap(env: ToolEnv) -> None:
    result = invoke(env, ["doctor"])
    assert result.exit_code == 0, result.output
    gaps = [f"GAP {emitter.agent} {name}={cap['level']}"
            for emitter in emitters_for(AGENTS, env.sources)
            for name, cap in emitter.capabilities().model_dump().items() if cap["level"] != "native"]
    assert gaps, "expected at least one capability gap"
    assert [gap for gap in gaps if gap not in result.output] == []


def test_emitted_codex_and_opencode_configs_are_valid(env: ToolEnv) -> None:
    config = tomllib.loads((env.home / ".codex" / "config.toml").read_text())
    assert config["mcp_servers"]["awg"]["command"] == "awg"
    listed = codex_mcp_list(env.home)
    if listed is not None:
        assert [server["name"] for server in listed] == ["awg"]
    schema = json.loads(SCHEMA.read_text())
    errors = list(Draft202012Validator(schema).iter_errors(opencode_config(env.home)))
    assert errors == []
