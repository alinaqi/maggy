"""Region states against harness.lock, and the 3-way diff shown on conflicts."""

from __future__ import annotations

import difflib

from maggy.harness.lock import LockEntry


def classify(entry: LockEntry | None, disk: str | None, profile: str | None) -> str:
    """new (never written, and absent on disk or already the profile's text),
    clean, pinned (user's text kept via --take-mine and the profile has not
    moved since) or edited (a conflict). A value the user already has at a
    managed key that differs from the profile is edited, never silently
    replaced (first adoption). profile None means the region was dropped."""
    if entry is None:
        return "new" if disk is None or disk == profile else "edited"
    if not entry.matches(disk):
        return "edited"
    if entry.base is None:
        return "clean"
    return "pinned" if profile == entry.base else "edited"


def resolve(state: str, resolution: str | None, stale: bool) -> str:
    """Action for a region: write, keep, remove, forget or conflict.
    --take-profile also ends a pin: the profile text is written again."""
    if state == "edited" or (state == "pinned" and resolution == "take_profile"):
        actions = {"take_mine": "forget" if stale else "keep", "take_profile": "remove" if stale else "write"}
        return actions.get(resolution, "conflict")
    if stale:
        return "remove"
    return "keep" if state == "pinned" else "write"


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
