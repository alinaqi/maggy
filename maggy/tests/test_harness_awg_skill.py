"""Claude Code and Codex get AWG's skill too (RFC §2.2 AWG wiring: MCP + skill + AGENTS.md),
as a managed copy of <awg_repo>/plugins/<claude-code|codex>/skills/awg/SKILL.md."""

from __future__ import annotations

from pathlib import Path

import pytest
from harness_emitter_helpers import (
    awg_sources, fixture_profile, make_sources, project_scope, user_scope,
)

from maggy.harness.apply import apply_changes
from maggy.harness.emitters import ClaudeEmitter, CodexEmitter
from maggy.harness.emitters.skills import MARKER

SKILL_DIRS = {ClaudeEmitter: ".claude/skills", CodexEmitter: ".codex/skills"}


@pytest.mark.parametrize("emitter", [ClaudeEmitter, CodexEmitter])
def test_user_scope_gets_the_awg_skill(tmp_path: Path, emitter) -> None:
    scope = user_scope(tmp_path)
    changes = emitter(awg_sources(tmp_path)).plan(fixture_profile(), scope)
    apply_changes(changes, scope.context())
    skill = scope.home / SKILL_DIRS[emitter] / "awg" / "SKILL.md"
    assert MARKER in skill.read_text() and "# awg" in skill.read_text()


@pytest.mark.parametrize("emitter", [ClaudeEmitter, CodexEmitter])
def test_awg_skill_survives_a_second_apply(tmp_path: Path, emitter) -> None:
    scope = user_scope(tmp_path)
    made = emitter(awg_sources(tmp_path))
    apply_changes(made.plan(fixture_profile(), scope), scope.context())
    again = made.plan(fixture_profile(), scope)
    assert [c.kind for c in again if "awg" in c.path.parts] == ["unchanged"]


@pytest.mark.parametrize("emitter", [ClaudeEmitter, CodexEmitter])
def test_no_awg_skill_without_checkout_or_provider(tmp_path: Path, emitter) -> None:
    plain = emitter(make_sources(tmp_path)).plan(fixture_profile(), user_scope(tmp_path))
    off = emitter(awg_sources(tmp_path)).plan(
        fixture_profile(work={"provider": "none"}), user_scope(tmp_path))
    project = emitter(awg_sources(tmp_path)).plan(fixture_profile(), project_scope(tmp_path))
    for changes in (plain, off, project):
        assert not [c for c in changes if c.path.parent.name == "awg"]
