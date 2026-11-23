"""Permission mapping and edited managed skills."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from harness_emitter_helpers import (
    by_name, fixture_profile, make_sources, user_scope, write,
)

from maggy.harness.apply import apply_changes
from maggy.harness.emitters import ClaudeEmitter, CodexEmitter
from maggy.harness.emitters.skills import managed_text, plan_skills

LOCKED_DOWN = {"profiles": {"ro": {"write": False, "network": False, "shell": False}}}


def test_read_only_profile_maps_to_denies_and_codex_read_only(tmp_path: Path) -> None:
    profile = fixture_profile(permissions=LOCKED_DOWN, worker={"permission": "ro"})
    scope = user_scope(tmp_path)
    claude = ClaudeEmitter(make_sources(tmp_path)).plan(profile, scope)
    perms = json.loads(by_name(claude, "settings.json").after)["permissions"]
    assert perms == {"deny": ["Edit", "Write", "MultiEdit", "NotebookEdit",
                              "WebFetch", "WebSearch", "Bash"]}
    codex = CodexEmitter(make_sources(tmp_path)).plan(profile, scope)
    config = tomllib.loads(by_name(codex, "config.toml").after)
    assert config["sandbox_mode"] == "read-only" and "sandbox_workspace_write" not in config


def test_undefined_permission_profile_emits_no_codex_sandbox(tmp_path: Path) -> None:
    profile = fixture_profile(permissions={}, hooks={})
    scope = user_scope(tmp_path)
    claude = ClaudeEmitter(make_sources(tmp_path)).plan(profile, scope)
    assert not [c for c in claude if c.path.name == "settings.json"]
    codex = CodexEmitter(make_sources(tmp_path)).plan(profile, scope)
    config = tomllib.loads(by_name(codex, "config.toml").after)
    assert "sandbox_mode" not in config and "approval_policy" not in config
    assert "sandbox_workspace_write" not in config


def _edited_skill(tmp_path: Path):
    scope = user_scope(tmp_path)
    emitter = ClaudeEmitter(make_sources(tmp_path))
    apply_changes(emitter.plan(fixture_profile(), scope), scope.context())
    skill = scope.home / ".claude" / "skills" / "python" / "SKILL.md"
    write(skill, skill.read_text() + "\nmy note\n")
    return scope, emitter, skill


def test_edited_managed_skill_is_a_conflict_not_overwritten(tmp_path: Path) -> None:
    scope, emitter, skill = _edited_skill(tmp_path)
    changes = emitter.plan(fixture_profile(), scope)
    assert by_name(changes, "python/SKILL.md").status == "conflict"
    removal = emitter.plan(fixture_profile(skills=[]), scope)
    assert by_name(removal, "python/SKILL.md").status == "conflict"
    apply_changes(removal, scope.context())
    assert skill.read_text().endswith("my note\n")


def test_take_mine_keeps_edit_and_take_profile_restores(tmp_path: Path) -> None:
    scope, emitter, skill = _edited_skill(tmp_path)
    ctx = scope.context().model_copy(update={"resolution": "take_mine"})
    names = ["python", "react-web"]
    kept = by_name(plan_skills(names, skill.parent.parent, (emitter.sources, ctx)), "python/SKILL.md")
    assert kept.status == "ok" and kept.kind == "unchanged"
    ctx = ctx.model_copy(update={"resolution": "take_profile"})
    restored = by_name(plan_skills(names, skill.parent.parent, (emitter.sources, ctx)),
                       "python/SKILL.md")
    assert restored.kind == "update" and "my note" not in restored.after


def test_marker_without_frontmatter_goes_first() -> None:
    assert managed_text("# plain\n").startswith("<!-- maggy:managed-skill -->\n# plain")
