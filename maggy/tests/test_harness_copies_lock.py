"""Whole-file copies are deleted only when harness.lock records Maggy wrote them."""

from __future__ import annotations

from pathlib import Path

from harness_emitter_helpers import fixture_profile, make_sources, user_scope, write

from maggy.harness.apply import apply_changes
from maggy.harness.emitters import ClaudeEmitter


def _apply(emitter, profile, scope):
    changes = emitter.plan(profile, scope)
    report = apply_changes(changes, scope.context())
    assert not report.skipped, report.skipped
    return changes


def test_user_copy_of_a_managed_skill_is_never_deleted(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    emitter = ClaudeEmitter(make_sources(tmp_path))
    _apply(emitter, fixture_profile(skills=["python"]), scope)
    skills = scope.root / ".claude" / "skills"
    copy = write(skills / "my-python" / "SKILL.md",
                 (skills / "python" / "SKILL.md").read_text() + "\nmy own edits\n")
    changes = _apply(emitter, fixture_profile(skills=["python"]), scope)
    assert copy.is_file() and "my own edits" in copy.read_text()
    assert all(c.path != copy for c in changes)


def test_lock_recorded_copy_is_still_removed(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    emitter = ClaudeEmitter(make_sources(tmp_path))
    _apply(emitter, fixture_profile(skills=["python"]), scope)
    _apply(emitter, fixture_profile(skills=[]), scope)
    assert not (scope.root / ".claude" / "skills" / "python" / "SKILL.md").exists()
