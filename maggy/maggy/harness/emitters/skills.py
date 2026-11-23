"""Managed skill copies: <skills_dir>/<name>/SKILL.md, whole-file.

A copy carries MARKER right after its frontmatter (frontmatter must stay
first). Only marked files are updated or deleted; a same-named skill without
the marker belongs to the user and is reported as a conflict, never touched.
A managed copy edited since Maggy wrote it (harness.lock) is a conflict too.
"""

from __future__ import annotations

import re
from pathlib import Path

from maggy.harness.changes import FileChange, HarnessContext
from maggy.harness.emitters.base import EmitterSources
from maggy.harness.emitters.sources import skill_source
from maggy.harness.fs_safe import read_text
from maggy.harness.lock import load_lock, region_hash

MARKER = "<!-- maggy:managed-skill -->"
_FRONTMATTER = re.compile(r"\A---\r?\n.*?^---[ \t]*\r?\n", re.S | re.M)
Env = tuple[EmitterSources, HarnessContext]


def managed_text(source: str) -> str:
    found = _FRONTMATTER.match(source)
    cut = found.end() if found else 0
    return f"{source[:cut]}{MARKER}\n{source[cut:]}"


def plan_skills(names: list[str], skills_dir: Path, env: Env) -> list[FileChange]:
    sources, ctx = env
    edited = _edited_check(ctx)
    wanted = [_change(skills_dir / n / "SKILL.md", managed_text(skill_source(sources, n)), edited)
              for n in names]
    stale = sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.is_dir() else []
    removals = [_removal(p, edited) for p in stale if p.parent.name not in names]
    return [*wanted, *[r for r in removals if r is not None]]


def _edited_check(ctx: HarnessContext):
    lock = load_lock(ctx.lock_path)

    def edited(path: Path, text: str) -> str:
        """clean, or for a managed copy changed on disk: edited / keep (take_mine)."""
        entry = lock.get(path, "skill")
        if entry is None or entry.sha256 == region_hash(text) or ctx.resolution == "take_profile":
            return "clean"
        return "keep" if ctx.resolution == "take_mine" else "edited"
    return edited


def _base(path: Path, before: str | None, after: str | None) -> FileChange:
    return FileChange(path=path, kind="unchanged", before=before, after=after,
                      managed_ids=["skill"], region_texts={"skill": after} if after else {})


def _change(path: Path, text: str, edited) -> FileChange:
    before = read_text(path)
    if before is not None and MARKER not in before:
        return _base(path, before, before).model_copy(update={
            "status": "conflict", "reason": "existing skill is not managed by Maggy; left untouched"})
    state = edited(path, before) if before is not None else "clean"
    if state != "clean":
        update = {"status": "conflict", "reason": "managed skill edited on disk"}
        return _base(path, before, before).model_copy(update=update if state == "edited" else {})
    kind = "create" if before is None else "unchanged" if before == text else "update"
    return _base(path, before, text).model_copy(update={"kind": kind})


def _removal(path: Path, edited) -> FileChange | None:
    before = read_text(path)
    if before is None or MARKER not in before or edited(path, before) == "keep":
        return None
    if edited(path, before) == "edited":
        return _base(path, before, before).model_copy(update={
            "status": "conflict", "reason": "managed skill edited on disk; not removed"})
    return _base(path, before, None).model_copy(update={"kind": "delete"})
