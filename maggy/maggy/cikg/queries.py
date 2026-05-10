"""CIKG query functions — gap analysis and market scoring."""

from __future__ import annotations

from .graph import KnowledgeGraphService
from .models import MarketScore


def find_gaps(
    graph: KnowledgeGraphService,
    feature_name: str,
) -> MarketScore:
    """Score a feature against the competitive landscape."""
    competitors = graph.list_nodes("competitor")
    features = graph.list_nodes("feature")

    matching = [
        f for f in features
        if feature_name.lower() in f.name.lower()
    ]
    if not matching:
        return MarketScore(
            feature=feature_name, gap_count=len(competitors),
            threat_level="low", trend_alignment=0.0,
            recommendation=f"No competitor has '{feature_name}' "
                           f"— potential differentiator",
        )

    # Count competitors that have this feature
    have_it = 0
    for feat in matching:
        edges = graph.get_edges(feat.id, "in")
        have_it += len([
            e for e in edges if e.edge_type == "has_feature"
        ])

    gap = len(competitors) - have_it
    threat = "high" if have_it > len(competitors) * 0.7 else \
             "medium" if have_it > len(competitors) * 0.3 else \
             "low"

    rec = (
        f"{have_it}/{len(competitors)} competitors have this. "
        f"{'Table stakes — must have.' if threat == 'high' else ''}"
        f"{'Growing trend.' if threat == 'medium' else ''}"
        f"{'Differentiator opportunity.' if threat == 'low' else ''}"
    )

    return MarketScore(
        feature=feature_name, gap_count=gap,
        threat_level=threat, recommendation=rec.strip(),
    )


def compare_entities(
    graph: KnowledgeGraphService,
    id_a: str, id_b: str,
) -> dict:
    """Compare two entities by their features."""
    a_edges = graph.get_edges(id_a, "out")
    b_edges = graph.get_edges(id_b, "out")

    a_features = {
        e.target_id for e in a_edges
        if e.edge_type == "has_feature"
    }
    b_features = {
        e.target_id for e in b_edges
        if e.edge_type == "has_feature"
    }

    return {
        "shared": list(a_features & b_features),
        "only_a": list(a_features - b_features),
        "only_b": list(b_features - a_features),
    }


def get_landscape(
    graph: KnowledgeGraphService,
) -> dict:
    """Return competitive landscape summary."""
    competitors = graph.list_nodes("competitor")
    features = graph.list_nodes("feature")
    techs = graph.list_nodes("technology")
    return {
        "competitors": len(competitors),
        "features_tracked": len(features),
        "technologies": len(techs),
        "top_competitors": [
            c.name for c in competitors[:10]
        ],
    }
