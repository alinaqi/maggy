"""Collect local data and build shareable memories."""

from __future__ import annotations

from .memory import SharedMemory


def collect_scores(routing, peer_id: str) -> list[SharedMemory]:
    """Build shareable routing score memories."""
    if not routing:
        return []
    shares: list[SharedMemory] = []
    for entry in routing.get_heatmap():
        if entry.get("count", 0) < 5:
            continue
        key = f"score:{entry.get('model', '')}:{entry.get('task_type', '')}"
        shares.append(SharedMemory(
            key=key, memory_type="score",
            content=entry, source_peer=peer_id,
            confidence=min(entry.get("count", 0) / 20, 1.0),
        ))
    return shares


def collect_gaps(forge, peer_id: str) -> list[SharedMemory]:
    """Build shareable capability gap memories."""
    if not forge:
        return []
    shares: list[SharedMemory] = []
    for gap in forge.get_gaps():
        key = f"gap:{gap.get('name', '')}"
        shares.append(SharedMemory(
            key=key, memory_type="gap",
            content=gap, source_peer=peer_id,
        ))
    return shares


def collect_policies(introspector, peer_id: str) -> list[SharedMemory]:
    """Build shareable policy memories from recommendations."""
    if not introspector:
        return []
    report = introspector.get_report()
    if not report:
        return []
    shares: list[SharedMemory] = []
    for rec in report.recommendations:
        if rec.severity != "action":
            continue
        key = f"policy:{rec.category}"
        shares.append(SharedMemory(
            key=key, memory_type="policy",
            content={"message": rec.message, "suggestion": rec.suggestion},
            source_peer=peer_id,
        ))
    return shares


def collect_all_shares(app_state, peer_id: str) -> list[SharedMemory]:
    """Collect all shareable data from local services."""
    shares: list[SharedMemory] = []
    shares.extend(collect_scores(
        getattr(app_state, "routing", None), peer_id,
    ))
    shares.extend(collect_gaps(
        getattr(app_state, "forge", None), peer_id,
    ))
    shares.extend(collect_policies(
        getattr(app_state, "introspector", None), peer_id,
    ))
    return shares
