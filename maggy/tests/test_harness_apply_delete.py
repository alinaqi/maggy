"""apply: delete changes remove a file with a backup and drop its lock entry."""

from __future__ import annotations

from pathlib import Path

from harness_engine_helpers import make_ctx, write

from maggy.harness.apply import apply_changes
from maggy.harness.changes import FileChange
from maggy.harness.lock import load_lock, save_lock


def _delete(path: Path, before: str) -> FileChange:
    return FileChange(path=path, kind="delete", before=before, after=None, managed_ids=["skill"])


def test_delete_backs_up_removes_and_forgets(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    path = write(ctx.root / "skills" / "py" / "SKILL.md", "managed\n")
    lock = load_lock(ctx.lock_path)
    lock.record(path, {"skill": "managed\n"})
    save_lock(lock, ctx.lock_path)
    report = apply_changes([_delete(path, "managed\n")], ctx)
    assert not path.exists() and not path.parent.exists()
    assert (report.backup_dir / "skills" / "py" / "SKILL.md").read_text() == "managed\n"
    assert load_lock(ctx.lock_path).get(path, "skill") is None
    assert path in report.written


def test_delete_skipped_when_file_changed_since_plan(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    path = write(ctx.root / "SKILL.md", "edited\n")
    report = apply_changes([_delete(path, "managed\n")], ctx)
    assert path.read_text() == "edited\n" and str(path) in report.skipped


def test_delete_keeps_non_empty_directory(tmp_path: Path) -> None:
    ctx = make_ctx(tmp_path)
    path = write(ctx.root / "skills" / "py" / "SKILL.md", "managed\n")
    extra = write(ctx.root / "skills" / "py" / "notes.md", "mine\n")
    apply_changes([_delete(path, "managed\n")], ctx)
    assert not path.exists() and extra.read_text() == "mine\n"
