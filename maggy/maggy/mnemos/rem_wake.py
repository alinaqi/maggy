"""REM Phase 4: Wake State Reconstruction."""

from __future__ import annotations

from maggy.mnemos.constants import REM_TARGET_RATIO
from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import MnemoNode


def count_active_nodes(db: MnemosDB) -> int:
    """Count all ACTIVE nodes."""
    nodes = db.list_nodes()
    return sum(1 for n in nodes if n.status == "ACTIVE")


def select_wake_context(
    db: MnemosDB,
    pre_rem_count: int,
) -> list[MnemoNode]:
    """Select top nodes by activation_weight for wake context.

    Target: <= 50% of pre-REM node count.
    """
    target = max(int(pre_rem_count * REM_TARGET_RATIO), 1)
    nodes = db.list_nodes()
    active = [n for n in nodes if n.status == "ACTIVE"]
    active.sort(key=lambda n: n.activation_weight, reverse=True)
    return active[:target]


def build_wake_summary(nodes: list[MnemoNode]) -> str:
    """Build minimal context string."""
    lines = ["Wake context:"]
    for n in nodes:
        lines.append(f"  [{n.type}] {n.content[:60]}")
    return "\n".join(lines)


def run_wake_reconstruction(
    db: MnemosDB, pre_rem_count: int,
) -> dict:
    """Execute Phase 4."""
    wake = select_wake_context(db, pre_rem_count)
    summary = build_wake_summary(wake)
    return {
        "wake_nodes": len(wake),
        "pre_rem_count": pre_rem_count,
        "ratio": len(wake) / max(pre_rem_count, 1),
        "summary": summary,
    }
