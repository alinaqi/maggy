"""Whole-file managed copies (skills, pi extensions), recognised by a marker.

Only files carrying the marker are updated; a file at the same path without it
belongs to the user and is reported as a conflict, never touched. A managed
copy edited since Maggy wrote it (harness.lock) is a conflict too; --take-mine
keeps the edit durably (until the shipped copy changes), --take-profile
overwrites it. A file is deleted only when harness.lock records that Maggy
wrote that exact path: a user's copy of a managed file keeps the marker but
has no lock entry, so it is never removed.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from maggy.harness.changes import FileChange, HarnessContext
from maggy.harness.conflict import classify, resolve
from maggy.harness.fs_safe import read_text
from maggy.harness.lock import entry_for, load_lock


class CopyKind(BaseModel):
    marker: str
    rid: str
    label: str


class _Env:
    def __init__(self, ctx: HarnessContext, kind: CopyKind) -> None:
        self.ctx, self.kind = ctx, kind
        self.lock = load_lock(ctx.lock_path)

    def action(self, path: Path, disk: str, wanted: str | None) -> str:
        """write/keep (or remove/forget when wanted is None) or conflict."""
        entry = self.lock.get(path, self.kind.rid)
        return resolve(classify(entry, disk, wanted), self.ctx.resolution, wanted is None)

    def base(self, path: Path, before: str | None, after: str | None) -> FileChange:
        return FileChange(path=path, kind="unchanged", before=before, after=after,
                          managed_ids=[self.kind.rid], region_texts={self.kind.rid: after} if after else {})

    def kept(self, text: str, base: str | None = None) -> dict:
        return {"lock_entries": {self.kind.rid: entry_for(text, base=base)}}


def plan_copies(wanted: dict[Path, str], candidates: list[Path],
                env: tuple[HarnessContext, CopyKind]) -> list[FileChange]:
    """Changes for the wanted copies, plus deletes of managed candidates no longer wanted."""
    state = _Env(*env)
    changes = [_change(p, t, state) for p, t in wanted.items()]
    removals = [_removal(p, state) for p in candidates if p not in wanted]
    return [*changes, *[r for r in removals if r is not None]]


def _conflict(env: _Env, found: tuple[Path, str], reason: str) -> FileChange:
    path, before = found
    return env.base(path, before, before).model_copy(update={"status": "conflict", "reason": reason})


def _change(path: Path, text: str, env: _Env) -> FileChange:
    before = read_text(path)
    if before is not None and env.kind.marker not in before:
        return _conflict(env, (path, before), f"existing {env.kind.label} is not managed by Maggy; left untouched")
    action = env.action(path, before, text) if before is not None else "write"
    if action == "conflict":
        return _conflict(env, (path, before), f"managed {env.kind.label} edited on disk")
    if action == "keep":
        return env.base(path, before, before).model_copy(update=env.kept(before, text))
    kind = "create" if before is None else "unchanged" if before == text else "update"
    return env.base(path, before, text).model_copy(update={"kind": kind, **env.kept(text)})


def _removal(path: Path, env: _Env) -> FileChange | None:
    before = read_text(path)
    if before is None or env.kind.marker not in before or env.lock.get(path, env.kind.rid) is None:
        return None
    action = env.action(path, before, None)
    if action == "conflict":
        return _conflict(env, (path, before), f"managed {env.kind.label} edited on disk; not removed")
    if action == "forget":
        return env.base(path, before, before).model_copy(update={"lock_entries": {}})
    return env.base(path, before, None).model_copy(update={"kind": "delete"})
