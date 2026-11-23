"""Per-region decisions for one managed file: write, keep, remove, retain,
forget or conflict, and the lock entries that result.

A region is in the profile (spec.regions) or stale: in harness.lock for the
file but no longer in the profile. A stale region is removed only when every
agent that owns it is in this run; otherwise it is retained untouched.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from maggy.harness.changes import HarnessContext, ManagedFile
from maggy.harness.conflict import classify, resolve
from maggy.harness.fs_safe import real
from maggy.harness.lock import LockEntry, entry_for
from maggy.harness.region_keys import REMOVE, canonical
from maggy.harness.region_lists import full_list, is_list, key_of, on_disk, owned_text
from maggy.harness.regions import extract, parse_region, region_text


@dataclass
class Region:
    rid: str
    entry: LockEntry | None
    disk: str | None
    profile: str | None
    value: Any


def _previous(entry: LockEntry | None) -> list:
    return json.loads(entry.content) if entry and entry.content else []


def _disk_text(spec: ManagedFile, content: str | None, item: tuple[str, LockEntry | None]) -> str | None:
    rid, entry = item
    if not is_list(rid):
        return extract(spec.format, content, [rid])[rid]
    if entry is None:
        return None  # Maggy owns no entries yet; the user's stay beside its own
    return owned_text(on_disk(spec.format, content, rid), _previous(entry))


def regions_of(spec: ManagedFile, before: str | None, entries: dict[str, LockEntry]) -> list[Region]:
    rids = list(spec.regions) + [rid for rid in entries if rid not in spec.regions]
    out = []
    for rid in rids:
        value = spec.regions.get(rid, REMOVE)
        profile = None if value is REMOVE else region_text(spec.format, value)
        disk = _disk_text(spec, before, (rid, entries.get(rid)))
        out.append(Region(rid, entries.get(rid), disk, profile, value))
    return out


def decide(region: Region, ctx: HarnessContext) -> str:
    stale = region.profile is None
    if stale and not set(region.entry.agents) <= set(ctx.agents or []):
        return "retain"
    return resolve(classify(region.entry, region.disk, region.profile), ctx.resolution, stale)


def _ours(fmt: str, region: Region, action: str) -> Any:
    if action == "write":
        return region.value
    if action == "keep" and region.disk is not None:
        return parse_region(fmt, region.disk)
    return REMOVE


def render_value(spec: ManagedFile, before: str | None, decided: tuple[Region, str]) -> tuple[str, Any] | None:
    """(key, value) to render for a region, None when the file is left as is."""
    region, action = decided
    if action in ("retain", "forget", "conflict"):
        return None
    ours = _ours(spec.format, region, action)
    if not is_list(region.rid):
        return region.rid, ours
    members = [] if ours is REMOVE else ours
    current = on_disk(spec.format, before, region.rid)
    return key_of(region.rid), full_list(current, _previous(region.entry), members)


def lock_entry(spec: ManagedFile, after: str, decided: tuple[Region, str, HarnessContext]) -> LockEntry | None:
    region, action, ctx = decided
    if action == "retain":
        return region.entry
    if action not in ("write", "keep"):
        return None
    run = set(ctx.agents or [])
    owners = set(spec.owners.get(region.rid, [])) | (set(region.entry.agents if region.entry else []) - run)
    meta = {"format": spec.format, "agents": sorted(owners), "root": str(real(ctx.root))}
    if action == "keep":
        return entry_for(region.disk, base=region.profile, **meta)
    text = canonical(region.value) if is_list(region.rid) else extract(spec.format, after, [region.rid])[region.rid]
    return entry_for(text, **meta)
