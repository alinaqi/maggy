"""OpenCode emitter: opencode.json keys checked against the real opencode 1.19.6 schema.

The fixture tests/fixtures/harness/opencode-1.19.6-config.schema.json is
components.schemas.Config (with its refs) from GET /doc of `opencode serve`,
run from the installed opencode-ai@1.19.6 npm package; its version is recorded
in the fixture's x-opencode-version.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from harness_emitter_helpers import (
    awg_sources, by_name, fixture_profile, make_sources, project_scope, user_scope,
)
from jsonschema import Draft202012Validator

from maggy.harness.emitters import OpenCodeEmitter

SCHEMA = Path(__file__).parent / "fixtures" / "harness" / "opencode-1.19.6-config.schema.json"


def _config(tmp_path: Path, scope, profile=None) -> dict:
    changes = OpenCodeEmitter(awg_sources(tmp_path)).plan(profile or fixture_profile(), scope)
    return json.loads(by_name(changes, "opencode.json").after)


def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA.read_text())
    assert schema["x-opencode-version"] == "1.19.6"
    return Draft202012Validator(schema)


@pytest.mark.parametrize("make_scope", [user_scope, project_scope])
def test_emitted_config_validates_against_opencode_1_19_6_schema(tmp_path: Path, make_scope) -> None:
    validator = _validator()
    for profile in (fixture_profile(), fixture_profile(permissions={"profiles": {"workspace": {
            "write": False, "network": True, "shell": True}}})):
        config = _config(tmp_path, make_scope(tmp_path), profile)
        assert not list(validator.iter_errors(config)), list(validator.iter_errors(config))


def test_schema_fixture_rejects_unknown_keys() -> None:
    assert not _validator().is_valid({"mcpServers": {}})


def test_user_scope_paths_honor_xdg_config_home(tmp_path: Path, monkeypatch) -> None:
    scope = user_scope(tmp_path)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(scope.home / "xdg"))
    changes = OpenCodeEmitter(awg_sources(tmp_path)).plan(fixture_profile(), scope)
    paths = {str(c.path.relative_to(scope.home)) for c in changes}
    assert {"xdg/opencode/opencode.json", "xdg/opencode/AGENTS.md",
            "xdg/opencode/skills/python/SKILL.md"} <= paths


def test_user_scope_defaults_to_dot_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    scope = user_scope(tmp_path)
    changes = OpenCodeEmitter(awg_sources(tmp_path)).plan(fixture_profile(), scope)
    assert by_name(changes, "opencode.json").path == scope.home / ".config" / "opencode" / "opencode.json"


def test_awg_mcp_plugin_and_skill_wiring(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    scope = user_scope(tmp_path)
    config = _config(tmp_path, scope)
    token = str(scope.home / ".maggy" / "tokens" / "opencode.token")
    assert config["mcp"]["awg"] == {"type": "local", "command": ["awg", "mcp", "--token-file", token],
                                    "enabled": True}
    repo = tmp_path / "awg-repo" / "plugins" / "opencode"
    assert config["plugin"] == [[f"file://{repo}/plugin/awg.js", {"tokenFile": token}]]
    assert config["skills"]["paths"] == [str(repo / "skills")]
    assert config["instructions"] == [str(scope.home / ".config" / "opencode" / "AGENTS.md")]


def test_project_scope_uses_env_home_and_no_machine_paths(tmp_path: Path) -> None:
    scope = project_scope(tmp_path)
    config = _config(tmp_path, scope)
    assert config["mcp"]["awg"]["command"][-1] == "{env:HOME}/.maggy/tokens/opencode.token"
    assert config["instructions"] == ["AGENTS.md"]
    assert "plugin" not in config and "skills" not in config
    assert str(tmp_path) not in json.dumps(config)


def test_permissions_mapped_from_profile(tmp_path: Path) -> None:
    config = _config(tmp_path, user_scope(tmp_path))
    assert config["permission"] == {"edit": "allow",
                                    "bash": {"*": "ask", "pytest -q": "allow", "ruff check .": "allow"}}
    locked = fixture_profile(permissions={"profiles": {"workspace": {
        "write": False, "network": False, "shell": False}}})
    assert _config(tmp_path, user_scope(tmp_path), locked)["permission"] == {
        "edit": "deny", "webfetch": "deny", "websearch": "deny", "bash": "deny"}


def test_no_awg_without_awg_repo_keeps_mcp(tmp_path: Path) -> None:
    changes = OpenCodeEmitter(make_sources(tmp_path)).plan(fixture_profile(), user_scope(tmp_path))
    config = json.loads(by_name(changes, "opencode.json").after)
    assert "awg" in config["mcp"] and "plugin" not in config and "skills" not in config
