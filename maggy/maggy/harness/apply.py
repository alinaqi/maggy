"""apply: write planned changes safely and record them in harness.lock.

Only changes with status ok are written. Every existing file is backed up to
<backups_dir>/<timestamp>/<path under root> before it is replaced; writes are
atomic (temp file + rename); paths whose resolved location leaves the root
are refused; files that reference token files get mode 0600.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from maggy.harness.changes import FileChange, HarnessContext
from maggy.harness.fs_safe import atomic_write, backup_file, inside_root, read_text, real, target_mode
from maggy.harness.lock import HarnessLock, load_lock, save_lock


class ApplyReport(BaseModel):
    written: list[Path] = Field(default_factory=list)
    skipped: dict[str, str] = Field(default_factory=dict)
    backup_dir: Path | None = None


def apply_changes(changes: list[FileChange], ctx: HarnessContext) -> ApplyReport:
    lock = load_lock(ctx.lock_path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report = ApplyReport(backup_dir=ctx.backups_dir / stamp)
    for change in changes:
        _apply_one(change, ctx, (lock, report))
    save_lock(lock, ctx.lock_path)
    if not report.backup_dir.exists():
        report.backup_dir = None
    return report


def _skip_reason(change: FileChange, root: Path) -> str | None:
    if change.status != "ok":
        return f"{change.status}: {change.reason}"
    if not inside_root(change.path, root):
        return "refused: path escapes the target root"
    if read_text(change.path) != change.before:
        return "changed on disk since plan; re-run plan"
    return None


def _apply_one(change: FileChange, ctx: HarnessContext, state: tuple[HarnessLock, ApplyReport]) -> None:
    lock, report = state
    reason = _skip_reason(change, ctx.root)
    if reason:
        report.skipped[str(change.path)] = reason
        return
    target = real(change.path)
    if change.kind != "unchanged":
        _write(change, (target, ctx.root), report)
    elif change.references_token:
        os.chmod(target, 0o600)
    lock.record(change.path, change.region_texts)


def _write(change: FileChange, where: tuple[Path, Path], report: ApplyReport) -> None:
    target, root = where
    if target.exists():
        backup_file(target, root, report.backup_dir)
    atomic_write(target, change.after or "", target_mode(target, change.references_token))
    report.written.append(change.path)
