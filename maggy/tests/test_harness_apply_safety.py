"""apply safety: backups, atomic writes, symlink escapes, token file modes."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from harness_engine_helpers import make_ctx, managed, write

from maggy.harness import apply as apply_mod
from maggy.harness.apply import apply_changes
from maggy.harness.changes import ManagedFile
from maggy.harness.plan import plan_files


def test_backup_taken_before_modification(tmp_path: Path, monkeypatch) -> None:
    ctx = make_ctx(tmp_path)
    path = write(ctx.root / "sub" / "AGENTS.md", "original\n")
    seen: list[str] = []
    real_replace = os.replace

    def spy(src, dst):
        if str(dst).endswith("AGENTS.md"):
            seen.extend(p.read_text() for p in ctx.backups_dir.rglob("AGENTS.md"))
        real_replace(src, dst)

    monkeypatch.setattr(apply_mod.os, "replace", spy)
    report = apply_changes(plan_files([managed(ctx, "sub/AGENTS.md", {"a": "x"})], ctx), ctx)
    assert seen == ["original\n"]
    assert (report.backup_dir / "sub" / "AGENTS.md").read_text() == "original\n"
    assert "x" in path.read_text()


def test_failed_write_leaves_original_and_no_temp(tmp_path: Path, monkeypatch) -> None:
    ctx = make_ctx(tmp_path)
    path = write(ctx.root / "AGENTS.md", "original\n")
    changes = plan_files([managed(ctx, "AGENTS.md", {"a": "x"})], ctx)

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(apply_mod.os, "replace", boom)
    with pytest.raises(OSError):
        apply_changes(changes, ctx)
    assert path.read_text() == "original\n"
    assert sorted(p.name for p in ctx.root.iterdir()) == ["AGENTS.md"]


def test_symlink_escaping_root_is_refused(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    outside = write(tmp_path / "outside" / "secret.md", "outside\n")
    (ctx.root / "link.md").symlink_to(outside)
    [change] = plan_files([managed(ctx, "link.md", {"a": "x"})], ctx)
    assert change.status == "refused"
    report = apply_changes([change], ctx)
    assert outside.read_text() == "outside\n" and not report.written


def test_symlinked_directory_escape_refused_for_new_file(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    (tmp_path / "elsewhere").mkdir()
    (ctx.root / "dir").symlink_to(tmp_path / "elsewhere")
    [change] = plan_files([managed(ctx, "dir/new.md", {"a": "x"})], ctx)
    apply_changes([change], ctx)
    assert change.status == "refused" and not (tmp_path / "elsewhere" / "new.md").exists()


def test_token_referencing_file_gets_mode_0600(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    spec = ManagedFile(path=ctx.root / "mcp.json", format="json",
                       regions={"mcp.awg.tokenFile": "~/.maggy/tokens/awg"}, references_token=True)
    apply_changes(plan_files([spec], ctx), ctx)
    assert stat.S_IMODE((ctx.root / "mcp.json").stat().st_mode) == 0o600
