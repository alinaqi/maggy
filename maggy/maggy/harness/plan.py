"""plan: what applying the managed regions would change, without writing."""

from __future__ import annotations

from typing import Any

from maggy.harness.changes import FileChange, HarnessContext, ManagedFile
from maggy.harness.conflict import find_conflicts, region_diff
from maggy.harness.fs_safe import inside_root, read_text
from maggy.harness.lock import load_lock
from maggy.harness.regions import RegionError, extract, parse_region, region_text, render


def plan_files(specs: list[ManagedFile], ctx: HarnessContext) -> list[FileChange]:
    planner = _Planner(ctx)
    return [planner.plan(spec) for spec in specs]


def _skip(spec: ManagedFile, before: str | None, **update: Any) -> FileChange:
    change = FileChange(
        path=spec.path, kind="unchanged", before=before, after=before,
        managed_ids=list(spec.regions), references_token=spec.references_token,
    )
    return change.model_copy(update=update)


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
        on_disk = extract(spec.format, before, list(spec.regions))
        conflicts = find_conflicts(spec, on_disk, self.lock) if before is not None else []
        if conflicts and self.ctx.resolution is None:
            return _skip(spec, before, status="conflict", conflicts=conflicts,
                         reason="managed region edited on disk",
                         diff3=self._diff3(spec, on_disk, conflicts))
        regions = self._resolved(spec, on_disk, conflicts)
        after = render(spec.format, before, regions)
        texts = {k: v for k, v in extract(spec.format, after, list(regions)).items() if v is not None}
        kind = "create" if before is None else "unchanged" if after == before else "update"
        update = {"kind": kind, "after": after, "region_texts": texts}
        return _skip(spec, before, **update)

    def _resolved(self, spec: ManagedFile, on_disk: dict, conflicts: list[str]) -> dict:
        if self.ctx.resolution != "take_mine":
            return dict(spec.regions)
        mine = {rid: on_disk[rid] for rid in conflicts}
        kept = {rid: v for rid, v in spec.regions.items() if rid not in conflicts}
        adopted = {rid: parse_region(spec.format, t) for rid, t in mine.items() if t is not None}
        return {**kept, **adopted}

    def _diff3(self, spec: ManagedFile, on_disk: dict, conflicts: list[str]) -> str:
        parts = []
        for rid in conflicts:
            last = self.lock.get(spec.path, rid).content
            profile = region_text(spec.format, spec.regions[rid])
            parts.append(region_diff(rid, (last, on_disk[rid], profile)))
        return "\n".join(parts)
