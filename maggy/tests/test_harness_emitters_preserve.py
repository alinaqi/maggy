"""Emitters never clobber user content; Maggy-managed skills are removable."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from harness_emitter_helpers import (
    by_name, fixture_profile, make_sources, project_scope, user_scope, write,
)

from maggy.harness.apply import apply_changes
from maggy.harness.emitters import ClaudeEmitter, CodexEmitter

USER_HOOK = {"matcher": "Bash", "hooks": [{"type": "command", "command": "~/bin/guard"}]}
USER_SETTINGS = {
    "theme": "dark",
    "permissions": {"allow": ["Bash(git status)"], "deny": ["Read(.env)"]},
    "hooks": {"PostToolUse": [USER_HOOK]},
}


def _apply(emitter, profile, scope):
    changes = emitter.plan(profile, scope)
    report = apply_changes(changes, scope.context())
    assert not report.skipped, report.skipped
    return changes


def test_claude_user_content_preserved(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    claude_md = write(scope.home / ".claude" / "CLAUDE.md", "# My rules\n\nBe terse.\n")
    settings = write(scope.home / ".claude" / "settings.json", json.dumps(USER_SETTINGS, indent=2))
    _apply(ClaudeEmitter(make_sources(tmp_path)), fixture_profile(), scope)
    assert claude_md.read_text().startswith("# My rules\n\nBe terse.\n")
    assert "@AGENTS.md" in claude_md.read_text()
    data = json.loads(settings.read_text())
    assert data["theme"] == "dark"
    assert data["permissions"]["allow"][0] == "Bash(git status)"
    assert "Bash(pytest -q)" in data["permissions"]["allow"]
    assert data["permissions"]["deny"] == ["Read(.env)"]
    assert data["hooks"]["PostToolUse"][0] == USER_HOOK
    assert len(data["hooks"]["PostToolUse"]) == 2


def test_claude_removed_hook_drops_only_maggy_entries(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    settings = write(scope.home / ".claude" / "settings.json", json.dumps(USER_SETTINGS, indent=2))
    emitter = ClaudeEmitter(make_sources(tmp_path))
    _apply(emitter, fixture_profile(), scope)
    _apply(emitter, fixture_profile(hooks={}), scope)
    hooks = json.loads(settings.read_text())["hooks"]
    assert hooks["PostToolUse"] == [USER_HOOK]
    assert ".maggy/hooks" not in json.dumps(hooks)


def test_codex_user_content_preserved(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    original = '# my codex\nmodel = "o3"  # keep\n\n[mcp_servers.other]\ncommand = "x"\n'
    config = write(scope.home / ".codex" / "config.toml", original)
    agents = write(scope.home / ".codex" / "AGENTS.md", "# Personal\n\nmine\n")
    _apply(CodexEmitter(make_sources(tmp_path)), fixture_profile(), scope)
    assert config.read_text().startswith('# my codex\nmodel = "o3"  # keep\n')
    parsed = tomllib.loads(config.read_text())
    assert parsed["mcp_servers"]["other"] == {"command": "x"}
    assert "awg" in parsed["mcp_servers"]
    assert agents.read_text().startswith("# Personal\n\nmine\n")


def test_removed_skill_deletes_only_maggy_managed(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    mine = write(scope.home / ".claude" / "skills" / "mine" / "SKILL.md", "---\nname: mine\n---\n")
    emitter = ClaudeEmitter(make_sources(tmp_path))
    _apply(emitter, fixture_profile(), scope)
    python = scope.home / ".claude" / "skills" / "python" / "SKILL.md"
    assert "maggy:managed-skill" in python.read_text()
    changes = _apply(emitter, fixture_profile(skills=["react-web"]), scope)
    assert by_name(changes, "python/SKILL.md").kind == "delete"
    assert not python.exists()
    assert mine.read_text() == "---\nname: mine\n---\n"
    assert (scope.home / ".claude" / "skills" / "react-web" / "SKILL.md").exists()


def test_user_skill_with_same_name_is_not_overwritten(tmp_path: Path) -> None:
    scope = project_scope(tmp_path)
    own = write(scope.root / ".agents" / "skills" / "python" / "SKILL.md", "my python\n")
    changes = CodexEmitter(make_sources(tmp_path)).plan(fixture_profile(), scope)
    change = by_name(changes, "python/SKILL.md")
    assert change.status == "conflict" and "not managed by Maggy" in change.reason
    apply_changes(changes, scope.context())
    assert own.read_text() == "my python\n"


def test_skill_frontmatter_stays_first(tmp_path: Path) -> None:
    changes = ClaudeEmitter(make_sources(tmp_path)).plan(fixture_profile(), user_scope(tmp_path))
    assert by_name(changes, "python/SKILL.md").after.startswith("---\nname: python\n")


def test_reapply_is_unchanged(tmp_path: Path) -> None:
    scope = project_scope(tmp_path)
    for emitter in (ClaudeEmitter(make_sources(tmp_path)), CodexEmitter(make_sources(tmp_path))):
        _apply(emitter, fixture_profile(), scope)
        again = emitter.plan(fixture_profile(), scope)
        assert {(c.kind, c.status) for c in again} == {("unchanged", "ok")}
