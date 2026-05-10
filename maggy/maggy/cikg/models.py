"""CIKG node and edge models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

NODE_TYPES = (
    "competitor", "feature", "market_segment",
    "technology", "trend", "product",
)

EDGE_TYPES = (
    "has_feature", "competes_with", "uses_technology",
    "targets_segment", "related_to",
)


@dataclass
class Node:
    """A node in the knowledge graph."""

    id: str
    node_type: str
    name: str
    description: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


@dataclass
class Edge:
    """A directed edge between two nodes."""

    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class MarketScore:
    """Result of a market scoring query."""

    feature: str
    gap_count: int = 0
    threat_level: str = "low"  # low | medium | high
    trend_alignment: float = 0.0
    recommendation: str = ""
