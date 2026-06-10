"""Learning memory consolidator — decay, evict, detect trends."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

DECAY_FACTOR = 0.95
EXPIRE_THRESHOLD = 0.1
MAX_PER_NAMESPACE = 500

LEARNING_NAMESPACES = [
    "chat-feedback",
    "review-feedback",
    "pr-feedback",
    "error-patterns",
]


def consolidate(engram_store, namespace: str) -> dict:
    records = engram_store.query(
        namespace=namespace, active_only=True, limit=1000,
    )
    stats = {"decayed": 0, "expired": 0, "evicted": 0, "trends": 0}

    for r in records:
        new_conf = round(r.confidence * DECAY_FACTOR, 4)
        if new_conf < EXPIRE_THRESHOLD:
            r.supersede()
            stats["expired"] += 1
        else:
            r.confidence = new_conf
            stats["decayed"] += 1
        engram_store.write(r)

    active = [r for r in records if r.is_active]
    if len(active) > MAX_PER_NAMESPACE:
        by_conf = sorted(active, key=lambda r: r.confidence)
        to_evict = by_conf[: len(active) - MAX_PER_NAMESPACE]
        for r in to_evict:
            r.supersede()
            engram_store.write(r)
            stats["evicted"] += 1

    tag_groups: dict[str, int] = {}
    for r in active:
        for tag in r.tags:
            tag_groups[tag] = tag_groups.get(tag, 0) + 1
    for tag, count in tag_groups.items():
        if count >= 3 and tag not in ("chat", "review", "pr-review"):
            stats["trends"] += 1

    return stats


def consolidate_all(engram_store) -> dict:
    results = {}
    for ns in LEARNING_NAMESPACES:
        results[ns] = consolidate(engram_store, ns)
    return results
