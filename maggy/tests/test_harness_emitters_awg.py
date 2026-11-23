"""AWG wiring in emitted config: token files referenced, never inlined."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest
from harness_emitter_helpers import (
    by_name, fixture_profile, make_sources, project_scope, user_scope,
)

from maggy.harness.emitters import ClaudeEmitter, CodexEmitter

TOKEN_LITERALS = [
    re.compile(r"awg_[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)\b(token|secret|password|api_key)\b\s*[=:]\s*['\"][^'\"]+['\"]"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{16,}"),
    re.compile(r"AWG_TOKEN\s*="),
]


def _all_plans(tmp_path: Path):
    sources = make_sources(tmp_path)
    for emitter in (ClaudeEmitter(sources), CodexEmitter(sources)):
        for make_scope in (user_scope, project_scope):
            yield from emitter.plan(fixture_profile(), make_scope(tmp_path))


def test_codex_config_parses_and_wires_awg_with_token_file(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    changes = CodexEmitter(make_sources(tmp_path)).plan(fixture_profile(), scope)
    config = tomllib.loads(by_name(changes, ".codex/config.toml").after)
    awg = config["mcp_servers"]["awg"]
    token = str(scope.home / ".maggy" / "tokens" / "codex.token")
    assert awg == {"command": "awg", "args": ["mcp", "--token-file", token]}
    assert config["sandbox_mode"] == "workspace-write"
    assert config["approval_policy"] == "on-request"


def test_codex_agents_md_has_awg_section(tmp_path: Path) -> None:
    changes = CodexEmitter(make_sources(tmp_path)).plan(fixture_profile(), user_scope(tmp_path))
    text = by_name(changes, ".codex/AGENTS.md").after
    assert "<!-- maggy:begin awg -->" in text and "awg_next" in text


def test_claude_wires_awg_mcp_with_token_file(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    changes = ClaudeEmitter(make_sources(tmp_path)).plan(fixture_profile(), scope)
    server = json.loads(by_name(changes, ".claude.json").after)["mcpServers"]["awg"]
    token = str(scope.home / ".maggy" / "tokens" / "claude.token")
    assert server == {"type": "stdio", "command": "awg", "args": ["mcp", "--token-file", token]}


def test_claude_project_mcp_uses_home_variable_not_absolute_home(tmp_path: Path) -> None:
    scope = project_scope(tmp_path)
    changes = ClaudeEmitter(make_sources(tmp_path)).plan(fixture_profile(), scope)
    text = by_name(changes, ".mcp.json").after
    assert "${HOME}/.maggy/tokens/claude.token" in text
    assert str(scope.home) not in text


def test_token_referencing_files_are_flagged(tmp_path: Path) -> None:
    flagged = {c.path.name for c in _all_plans(tmp_path) if c.references_token}
    assert {"config.toml", ".claude.json", ".mcp.json"} <= flagged


def test_no_token_literals_in_any_emitted_file(tmp_path: Path) -> None:
    for change in _all_plans(tmp_path):
        for pattern in TOKEN_LITERALS:
            assert not pattern.search(change.after or ""), (change.path, pattern.pattern)


def test_plan_does_not_mint_tokens(tmp_path: Path) -> None:
    list(_all_plans(tmp_path))
    assert not (tmp_path / "home" / ".maggy" / "tokens").exists()


@pytest.mark.parametrize("emitter_cls", [ClaudeEmitter, CodexEmitter])
def test_no_awg_wiring_when_work_provider_none(tmp_path: Path, emitter_cls) -> None:
    profile = fixture_profile(work={"provider": "none"})
    changes = emitter_cls(make_sources(tmp_path)).plan(profile, user_scope(tmp_path))
    assert not any("awg" in (c.after or "").lower() for c in changes)
