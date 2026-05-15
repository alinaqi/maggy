"""REM Phase 1: Slow-Wave — batch compress and evict."""

from __future__ import annotations

from maggy.mnemos.constants import COMPRESS_BATCH_SIZE, EVICTION_WEIGHT_THRESHOLD
from maggy.mnemos.consolidation import compress_nodes, evict_nodes
from maggy.mnemos.db import MnemosDB
from maggy.mnemos.db_queries import list_nodes_below_weight
from maggy.mnemos.models import MnemoNode


def select_result_nodes(db: MnemosDB) -> list[MnemoNode]:
    """All ACTIVE ResultNodes, oldest first."""
    nodes = db.list_nodes(node_type="ResultNode")
    active = [n for n in nodes if n.status == "ACTIVE"]
    active.sort(key=lambda n: n.created_at)
    return active


def batch_compress(
    db: MnemosDB,
    nodes: list[MnemoNode],
    batch_size: int = COMPRESS_BATCH_SIZE,
) -> int:
    """Compress ResultNodes in batches. Returns count."""
    compressed = 0
    for i in range(0, len(nodes), batch_size):
        batch = nodes[i:i + batch_size]
        compress_nodes(db, batch)
        compressed += len(batch)
    return compressed


def evict_cold_context_nodes(db: MnemosDB) -> int:
    """Evict ContextNodes below activation weight."""
    cold = list_nodes_below_weight(
        db.conn, EVICTION_WEIGHT_THRESHOLD,
        node_type="ContextNode",
    )
    return evict_nodes(db, cold)


def run_slow_wave(db: MnemosDB) -> dict:
    """Execute Phase 1."""
    results = select_result_nodes(db)
    compressed = batch_compress(db, results)
    evicted = evict_cold_context_nodes(db)
    return {"compressed": compressed, "evicted": evicted}
