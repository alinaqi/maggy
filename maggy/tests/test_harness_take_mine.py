"""--take-mine is durable: the kept text survives later plain applies until
the profile itself changes, which is then reported as a conflict."""

from __future__ import annotations

from pathlib import Path

from harness_engine_helpers import make_ctx, managed, write
from harness_emitter_helpers import fixture_profile, make_sources, user_scope

from maggy.harness.apply import apply_changes
from maggy.harness.emitters import ClaudeEmitter
from maggy.harness.plan import plan_files

BLOCK = "<!-- maggy:begin awg -->\n{}\n<!-- maggy:end awg -->\n"


def _taken(tmp_path: Path) -> Path:
    ctx = make_ctx(tmp_path)
    path = write(ctx.root / "AGENTS.md", "")
    apply_changes(plan_files([managed(ctx, "AGENTS.md", {"awg": "v1"})], ctx), ctx)
    path.write_text(BLOCK.format("mine"))
    mine = make_ctx(tmp_path, "take_mine")
    apply_changes(plan_files([managed(mine, "AGENTS.md", {"awg": "v1"})], mine), mine)
    return path


def test_plain_apply_after_take_mine_keeps_the_edit(tmp_path: Path) -> None:
    path = _taken(tmp_path)
    ctx = make_ctx(tmp_path)
    for _ in range(2):
        [change] = plan_files([managed(ctx, "AGENTS.md", {"awg": "v1"})], ctx)
        assert (change.status, change.kind) == ("ok", "unchanged")
        apply_changes([change], ctx)
    assert path.read_text() == BLOCK.format("mine")


def test_profile_change_after_take_mine_is_a_conflict(tmp_path: Path) -> None:
    _taken(tmp_path)
    ctx = make_ctx(tmp_path)
    [change] = plan_files([managed(ctx, "AGENTS.md", {"awg": "v2"})], ctx)
    assert change.status == "conflict" and "+v2" in change.diff3 and "mine" in change.diff3


def test_take_profile_ends_the_pin(tmp_path: Path) -> None:
    path = _taken(tmp_path)
    theirs = make_ctx(tmp_path, "take_profile")
    apply_changes(plan_files([managed(theirs, "AGENTS.md", {"awg": "v1"})], theirs), theirs)
    assert path.read_text() == BLOCK.format("v1")
    ctx = make_ctx(tmp_path)
    [change] = plan_files([managed(ctx, "AGENTS.md", {"awg": "v2"})], ctx)
    assert (change.status, change.kind) == ("ok", "update")


def test_take_mine_on_a_skill_copy_is_durable(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    emitter = ClaudeEmitter(make_sources(tmp_path))
    apply_changes(emitter.plan(fixture_profile(), scope), scope.context())
    skill = scope.root / ".claude" / "skills" / "python" / "SKILL.md"
    skill.write_text(skill.read_text() + "\nmy notes\n")
    mine = scope.model_copy(update={"resolution": "take_mine"})
    apply_changes(emitter.plan(fixture_profile(), mine), mine.context())
    changes = emitter.plan(fixture_profile(), scope)
    apply_changes(changes, scope.context())
    assert "my notes" in skill.read_text()
    [change] = [c for c in changes if c.path == skill]
    assert (change.status, change.kind) == ("ok", "unchanged")
