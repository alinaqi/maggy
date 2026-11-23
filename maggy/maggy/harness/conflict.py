"""Conflict detection and the 3-way diff shown to the user."""

from __future__ import annotations

import difflib

from maggy.harness.changes import ManagedFile
from maggy.harness.lock import HarnessLock, region_hash


def find_conflicts(spec: ManagedFile, on_disk: dict, lock: HarnessLock) -> list[str]:
    """Regions whose on-disk text no longer matches what Maggy last wrote."""
    out = []
    for rid in spec.regions:
        entry = lock.get(spec.path, rid)
        disk = on_disk.get(rid)
        if entry and (disk is None or region_hash(disk) != entry.sha256):
            out.append(rid)
    return out


def _diff(old: str, new: str, names: tuple[str, str]) -> list[str]:
    lines = difflib.unified_diff(
        old.splitlines(), new.splitlines(), fromfile=names[0], tofile=names[1], lineterm="",
    )
    return list(lines)


def region_diff(rid: str, versions: tuple[str, str | None, str]) -> str:
    """last-written vs on-disk and last-written vs profile for one region."""
    last, disk, profile = versions
    head = [f"=== region {rid}: last-written vs on-disk vs profile ==="]
    mine = _diff(last, disk or "", ("last-written", "on-disk"))
    theirs = _diff(last, profile, ("last-written", "profile"))
    return "\n".join(head + mine + theirs)
