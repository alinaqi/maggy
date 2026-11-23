"""Conflicts: user edits inside a managed region, 3-way diff, resolutions."""

from __future__ import annotations

import json
from pathlib import Path

from harness_engine_helpers import make_ctx, managed, write

from maggy.harness.apply import apply_changes
from maggy.harness.lock import load_lock, region_hash
from maggy.harness.plan import plan_files

BLOCK = "<!-- maggy:begin awg -->\n{}\n<!-- maggy:end awg -->\n"


def _edited(tmp_path: Path, resolution: str | None = None):
    """Apply 'v1', user edits the block to 'mine', profile now wants 'v2'."""
    ctx = make_ctx(tmp_path)
    path = write(ctx.root / "AGENTS.md", "head\n")
    apply_changes(plan_files([managed(ctx, "AGENTS.md", {"awg": "v1"})], ctx), ctx)
    path.write_text("head\n\n" + BLOCK.format("mine") + "user tail\n")
    ctx = make_ctx(tmp_path, resolution)
    return ctx, path, [managed(ctx, "AGENTS.md", {"awg": "v2"})]


def test_edit_inside_region_is_a_conflict_and_apply_skips(tmp_path: Path) -> None:
    ctx, path, specs = _edited(tmp_path)
    [change] = plan_files(specs, ctx)
    assert change.status == "conflict" and change.conflicts == ["awg"]
    report = apply_changes([change], ctx)
    assert "mine" in path.read_text() and not report.written
    assert str(path) in report.skipped


def test_conflict_produces_three_way_diff(tmp_path: Path) -> None:
    ctx, _, specs = _edited(tmp_path)
    [change] = plan_files(specs, ctx)
    diff = change.diff3
    assert "last-written" in diff and "on-disk" in diff and "profile" in diff
    assert "-v1" in diff and "+mine" in diff and "+v2" in diff


def test_take_mine_adopts_on_disk_and_updates_lock(tmp_path: Path) -> None:
    ctx, path, specs = _edited(tmp_path, "take_mine")
    [change] = plan_files(specs, ctx)
    assert change.status == "ok" and change.kind == "unchanged"
    apply_changes([change], ctx)
    assert "mine" in path.read_text()
    assert load_lock(ctx.lock_path).get(path, "awg").sha256 == region_hash("mine")
    again = plan_files(specs, make_ctx(tmp_path))
    assert (again[0].status, again[0].kind) == ("ok", "unchanged")


def test_take_profile_overwrites_region_only(tmp_path: Path) -> None:
    ctx, path, specs = _edited(tmp_path, "take_profile")
    [change] = plan_files(specs, ctx)
    apply_changes([change], ctx)
    assert path.read_text() == "head\n\n" + BLOCK.format("v2") + "user tail\n"
    assert plan_files(specs, make_ctx(tmp_path))[0].kind == "unchanged"


def test_json_key_edit_is_a_conflict(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    path = write(ctx.root / "s.json", "{}\n")
    specs = [managed(ctx, "s.json", {"mcp.awg": {"cmd": "a"}})]
    apply_changes(plan_files(specs, ctx), ctx)
    data = json.loads(path.read_text())
    data["mcp"]["awg"]["cmd"] = "edited"
    path.write_text(json.dumps(data))
    assert plan_files(specs, ctx)[0].status == "conflict"


def test_unedited_region_is_not_a_conflict(tmp_path: Path) -> None:
    ctx, path, specs = _edited(tmp_path)
    path.write_text("head\n\n" + BLOCK.format("v1") + "user tail edited\n")
    assert plan_files(specs, ctx)[0].status == "ok"
