"""Micro-consolidation at COMPRESS fatigue range."""

from __future__ import annotations

from maggy.mnemos.constants import (
    COMPRESS_BATCH_SIZE,
    EVICTION_WEIGHT_THRESHOLD,
    MICRO_CONSOLIDATION_MAX,
    MICRO_CONSOLIDATION_MIN,
)
from maggy.mnemos.db import MnemosDB
from maggy.mnemos.db_queries import (
    bulk_update_status,
    list_nodes_below_weight,
    update_node_status,
    update_node_summary,
)
from maggy.mnemos.models import MnemoNode


def should_consolidate(fatigue_score: float) -> bool:
    """True if fatigue is in COMPRESS range."""
    return (
        MICRO_CONSOLIDATION_MIN
        <= fatigue_score
        < MICRO_CONSOLIDATION_MAX
    )


def select_compress_candidates(
    db: MnemosDB,
) -> list[MnemoNode]:
    """Select oldest ACTIVE ResultNodes for compression."""
    nodes = db.list_nodes(node_type="ResultNode")
    active = [n for n in nodes if n.status == "ACTIVE"]
    active.sort(key=lambda n: n.created_at)
    return active[:COMPRESS_BATCH_SIZE]


def compress_nodes(
    db: MnemosDB, nodes: list[MnemoNode],
) -> str:
    """Compress batch into summary. Mark COMPRESSED."""
    parts = [n.content[:60] for n in nodes]
    summary = "; ".join(parts)
    ids = [n.id for n in nodes]
    for nid in ids:
        update_node_status(db.conn, nid, "COMPRESSED")
        update_node_summary(db.conn, nid, summary)
    return summary


def select_evict_candidates(
    db: MnemosDB,
) -> list[MnemoNode]:
    """ContextNodes with low activation weight."""
    return list_nodes_below_weight(
        db.conn,
        EVICTION_WEIGHT_THRESHOLD,
        node_type="ContextNode",
    )


def evict_nodes(
    db: MnemosDB, nodes: list[MnemoNode],
) -> int:
    """Mark nodes as EVICTED. Returns count."""
    ids = [n.id for n in nodes]
    return bulk_update_status(db.conn, ids, "EVICTED")


def run_micro_consolidation(
    db: MnemosDB, fatigue_score: float,
) -> dict:
    """Full micro-consolidation pass."""
    if not should_consolidate(fatigue_score):
        return {"compressed": 0, "evicted": 0}
    candidates = select_compress_candidates(db)
    compress_nodes(db, candidates)
    evict_cands = select_evict_candidates(db)
    evicted = evict_nodes(db, evict_cands)
    return {
        "compressed": len(candidates),
        "evicted": evicted,
    }
