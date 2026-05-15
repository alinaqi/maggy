"""Activation weight computation for MnemoNodes."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from maggy.mnemos.constants import (
    WEIGHT_CENTRALITY,
    WEIGHT_FREQUENCY,
    WEIGHT_RECENCY,
)
from maggy.mnemos.models import MnemoNode, NodeLink

# Half-life for recency decay (seconds)
_HALF_LIFE_S = 3600.0  # 1 hour


def compute_recency_score(node: MnemoNode) -> float:
    """Exponential decay from last_accessed. 1.0 = now."""
    now = datetime.now(timezone.utc)
    age_s = (now - node.last_accessed).total_seconds()
    return math.exp(-0.693 * age_s / _HALF_LIFE_S)


def compute_frequency_score(node: MnemoNode) -> float:
    """Log-normalized access count. 0.0-1.0."""
    if node.access_count <= 0:
        return 0.0
    return min(math.log1p(node.access_count) / 5.0, 1.0)


def compute_centrality_score(
    node_id: str, links: list[NodeLink],
) -> float:
    """Degree centrality: edges touching node / total edges."""
    if not links:
        return 0.0
    count = sum(
        1 for lk in links
        if lk.source_id == node_id or lk.target_id == node_id
    )
    return min(count / max(len(links), 1), 1.0)


def compute_activation_weight(
    node: MnemoNode, links: list[NodeLink],
) -> float:
    """Weighted composite activation weight."""
    r = compute_recency_score(node)
    f = compute_frequency_score(node)
    c = compute_centrality_score(node.id, links)
    return WEIGHT_RECENCY * r + WEIGHT_FREQUENCY * f + WEIGHT_CENTRALITY * c
