"""Regions dropped from the profile are removed from disk and from harness.lock."""

from __future__ import annotations

from pathlib import Path

from harness_engine_helpers import make_ctx, managed, write

from maggy.harness.apply import apply_changes
from maggy.harness.lock import load_lock
from maggy.harness.plan import plan_files

BLOCK = "<!-- maggy:begin {0} -->\n{1}\n<!-- maggy:end {0} -->\n"


def _applied(tmp_path: Path, resolution: str | None = None):
    """'rules' and 'awg' written; the profile now only wants 'rules'."""
    ctx = make_ctx(tmp_path)
    path = write(ctx.root / "AGENTS.md", "head\n")
    apply_changes(plan_files([managed(ctx, "AGENTS.md", {"rules": "R", "awg": "A"})], ctx), ctx)
    ctx = make_ctx(tmp_path, resolution)
    return ctx, path, [managed(ctx, "AGENTS.md", {"rules": "R"})]


def test_dropped_region_is_removed_and_forgotten(tmp_path: Path) -> None:
    ctx, path, specs = _applied(tmp_path)
    [change] = plan_files(specs, ctx)
    assert (change.status, change.kind) == ("ok", "update")
    apply_changes([change], ctx)
    assert path.read_text() == "head\n\n" + BLOCK.format("rules", "R")
    assert load_lock(ctx.lock_path).get(path, "awg") is None
    assert plan_files(specs, ctx)[0].kind == "unchanged"


def test_dropped_region_edited_on_disk_is_a_conflict(tmp_path: Path) -> None:
    ctx, path, specs = _applied(tmp_path)
    path.write_text(path.read_text().replace("\nA\n", "\nmine\n"))
    [change] = plan_files(specs, ctx)
    assert change.status == "conflict" and change.conflicts == ["awg"]
    assert "+mine" in change.diff3


def test_take_profile_removes_edited_region(tmp_path: Path) -> None:
    ctx, path, specs = _applied(tmp_path, "take_profile")
    path.write_text(path.read_text().replace("\nA\n", "\nmine\n"))
    apply_changes(plan_files(specs, ctx), ctx)
    assert "mine" not in path.read_text() and "maggy:begin awg" not in path.read_text()


def test_take_mine_keeps_edited_region_as_user_content(tmp_path: Path) -> None:
    ctx, path, specs = _applied(tmp_path, "take_mine")
    path.write_text(path.read_text().replace("\nA\n", "\nmine\n"))
    apply_changes(plan_files(specs, ctx), ctx)
    assert "mine" in path.read_text()
    assert load_lock(ctx.lock_path).get(path, "awg") is None
    again = plan_files(specs, make_ctx(tmp_path))[0]
    assert (again.status, again.kind) == ("ok", "unchanged")


def test_region_owned_by_an_agent_outside_the_run_is_kept(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path).model_copy(update={"agents": ["claude", "codex"]})
    path = write(ctx.root / "AGENTS.md", "")
    spec = managed(ctx, "AGENTS.md", {"rules": "R", "awg": "A"})
    spec = spec.model_copy(update={"owners": {"rules": ["claude", "codex"], "awg": ["codex"]}})
    apply_changes(plan_files([spec], ctx), ctx)
    claude_only = ctx.model_copy(update={"agents": ["claude"]})
    spec = managed(ctx, "AGENTS.md", {"rules": "R"}).model_copy(update={"owners": {"rules": ["claude"]}})
    apply_changes(plan_files([spec], claude_only), claude_only)
    lock = load_lock(ctx.lock_path)
    assert "maggy:begin awg" in path.read_text() and lock.get(path, "awg").agents == ["codex"]
    assert lock.get(path, "rules").agents == ["claude", "codex"]
