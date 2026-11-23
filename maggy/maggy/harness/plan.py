"""plan: what applying the managed regions would change, without writing.

Each region (in the profile, or stale: in harness.lock but dropped from the
profile) gets an action from plan_regions; any conflict skips the whole file.
"""

from __future__ import annotations

from typing import Any

from maggy.harness.changes import FileChange, HarnessContext, ManagedFile
from maggy.harness.conflict import region_diff
from maggy.harness.fs_safe import inside_root, read_text
from maggy.harness.lock import load_lock
from maggy.harness.plan_regions import Region, decide, lock_entry, regions_of, render_value
from maggy.harness.region_keys import REMOVE
from maggy.harness.regions import RegionError, render


def plan_files(specs: list[ManagedFile], ctx: HarnessContext) -> list[FileChange]:
    planner = _Planner(ctx)
    return [planner.plan(spec) for spec in specs]


def _skip(spec: ManagedFile, before: str | None, **update: Any) -> FileChange:
    change = FileChange(
        path=spec.path, kind="unchanged", before=before, after=before,
        managed_ids=list(spec.regions), references_token=spec.references_token,
    )
    return change.model_copy(update=update)


def _diff3(conflicts: list[Region]) -> str:
    return "\n".join(region_diff(r.rid, (r.entry.content or "", r.disk, r.profile or "")) for r in conflicts)


class _Planner:
    def __init__(self, ctx: HarnessContext) -> None:
        self.ctx = ctx
        self.lock = load_lock(ctx.lock_path)

    def plan(self, spec: ManagedFile) -> FileChange:
        if not inside_root(spec.path, self.ctx.root):
            return _skip(spec, None, status="refused", reason="path escapes the target root")
        before = read_text(spec.path)
        try:
            return self._plan(spec, before)
        except RegionError as exc:
            return _skip(spec, before, status="invalid", reason=str(exc))

    def _plan(self, spec: ManagedFile, before: str | None) -> FileChange:
        entries = self.lock.entries(spec.path) if before is not None else {}
        decided = [(r, decide(r, self.ctx)) for r in regions_of(spec, before, entries)]
        conflicts = [r for r, action in decided if action == "conflict"]
        if conflicts:
            return _skip(spec, before, status="conflict", conflicts=[r.rid for r in conflicts],
                         reason="managed region edited on disk", diff3=_diff3(conflicts))
        values = dict(v for v in (render_value(spec, before, d) for d in decided) if v is not None)
        if before is None and all(v is REMOVE for v in values.values()):
            return _skip(spec, None, lock_entries={})
        after = render(spec.format, before, values)
        found = {r.rid: lock_entry(spec, after, (r, a, self.ctx)) for r, a in decided}
        entries = {rid: e for rid, e in found.items() if e is not None}
        kind = "create" if before is None else "unchanged" if after == before else "update"
        texts = {rid: e.content for rid, e in entries.items() if e.content is not None}
        return _skip(spec, before, kind=kind, after=after, region_texts=texts, lock_entries=entries)
