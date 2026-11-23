"""Whole-file managed copies (skills, pi extensions), recognised by a marker.

Only files carrying the marker are updated or deleted; a file at the same path
without it belongs to the user and is reported as a conflict, never touched.
A managed copy edited since Maggy wrote it (harness.lock) is a conflict too.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from maggy.harness.changes import FileChange, HarnessContext
from maggy.harness.fs_safe import read_text
from maggy.harness.lock import load_lock, region_hash


class CopyKind(BaseModel):
    marker: str
    rid: str
    label: str


class _Env:
    def __init__(self, ctx: HarnessContext, kind: CopyKind) -> None:
        self.ctx, self.kind = ctx, kind
        self.lock = load_lock(ctx.lock_path)

    def state(self, path: Path, text: str) -> str:
        """clean, or for a managed copy changed on disk: edited / keep (take_mine)."""
        entry = self.lock.get(path, self.kind.rid)
        if entry is None or entry.sha256 == region_hash(text) or self.ctx.resolution == "take_profile":
            return "clean"
        return "keep" if self.ctx.resolution == "take_mine" else "edited"

    def base(self, path: Path, before: str | None, after: str | None) -> FileChange:
        texts = {self.kind.rid: after} if after else {}
        return FileChange(path=path, kind="unchanged", before=before, after=after,
                          managed_ids=[self.kind.rid], region_texts=texts)


def plan_copies(wanted: dict[Path, str], candidates: list[Path],
                env: tuple[HarnessContext, CopyKind]) -> list[FileChange]:
    """Changes for the wanted copies, plus deletes of managed candidates no longer wanted."""
    state = _Env(*env)
    changes = [_change(p, t, state) for p, t in wanted.items()]
    removals = [_removal(p, state) for p in candidates if p not in wanted]
    return [*changes, *[r for r in removals if r is not None]]


def _change(path: Path, text: str, env: _Env) -> FileChange:
    before = read_text(path)
    if before is not None and env.kind.marker not in before:
        return env.base(path, before, before).model_copy(update={
            "status": "conflict", "reason": f"existing {env.kind.label} is not managed by Maggy; left untouched"})
    state = env.state(path, before) if before is not None else "clean"
    if state != "clean":
        update = {"status": "conflict", "reason": f"managed {env.kind.label} edited on disk"}
        return env.base(path, before, before).model_copy(update=update if state == "edited" else {})
    kind = "create" if before is None else "unchanged" if before == text else "update"
    return env.base(path, before, text).model_copy(update={"kind": kind})


def _removal(path: Path, env: _Env) -> FileChange | None:
    before = read_text(path)
    if before is None or env.kind.marker not in before or env.state(path, before) == "keep":
        return None
    if env.state(path, before) == "edited":
        return env.base(path, before, before).model_copy(update={
            "status": "conflict", "reason": f"managed {env.kind.label} edited on disk; not removed"})
    return env.base(path, before, None).model_copy(update={"kind": "delete"})
