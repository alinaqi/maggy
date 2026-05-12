"""CIKG query functions — gap analysis and market scoring."""

from __future__ import annotations

from .graph import KnowledgeGraphService
from .models import MarketScore, Node


def find_gaps(graph: KnowledgeGraphService, feature_name: str) -> MarketScore:
    """Score a feature against the competitive landscape."""
    feature_ids = _matching_ids(graph, "feature", feature_name)
    results = []
    for node in graph.list_nodes("competitor"):
        has = bool(feature_ids & _targets_for(graph, node.id, "has_feature"))
        results.append({
            "entity_id": node.id, "entity": node.name,
            "feature": feature_name, "status": "has" if has else "lacks",
        })
    have_it = sum(1 for r in results if r["status"] == "has")
    total = len(results)
    threat = _threat_level(have_it, total)
    return MarketScore(
        feature=feature_name, gap_count=total - have_it,
        threat_level=threat,
        recommendation=_recommend(feature_name, have_it, total, threat),
    )


def find_gaps_raw(graph: KnowledgeGraphService, feature: str) -> list[dict]:
    """Return raw gap results per competitor."""
    feature_ids = _matching_ids(graph, "feature", feature)
    results = []
    for node in graph.list_nodes("competitor"):
        has = bool(feature_ids & _targets_for(graph, node.id, "has_feature"))
        results.append({
            "entity_id": node.id, "entity": node.name,
            "feature": feature, "status": "has" if has else "lacks",
        })
    return sorted(results, key=lambda r: r["entity"])


def compare_entities(graph: KnowledgeGraphService, id_a: str, id_b: str) -> dict:
    """Compare two entities by their features."""
    a_feat = _targets_for(graph, id_a, "has_feature")
    b_feat = _targets_for(graph, id_b, "has_feature")
    related = graph.get_edges(id_a, "out") + graph.get_edges(id_b, "out")
    rels = [
        {"source_id": e.source_id, "target_id": e.target_id, "edge_type": e.edge_type}
        for e in related if {e.source_id, e.target_id} == {id_a, id_b}
    ]
    return {
        "shared": sorted(a_feat & b_feat),
        "only_a": sorted(a_feat - b_feat),
        "only_b": sorted(b_feat - a_feat),
        "relationships": rels,
    }


def get_landscape(graph: KnowledgeGraphService) -> dict:
    """Return competitive landscape summary."""
    competitors = graph.list_nodes("competitor")
    features = graph.list_nodes("feature")
    techs = graph.list_nodes("technology")
    return {
        "competitors": len(competitors),
        "features_tracked": len(features),
        "technologies": len(techs),
        "top_competitors": [c.name for c in competitors[:10]],
    }


def get_segment_landscape(graph: KnowledgeGraphService, segment: str) -> dict:
    """Return landscape for a specific market segment."""
    seg_nodes = _matching_nodes(graph, "market_segment", segment)
    if not seg_nodes:
        return _empty_landscape(segment)
    seg_id = seg_nodes[0].id
    comp_ids = [
        e.source_id for e in graph.get_edges(seg_id, "in")
        if e.edge_type == "targets_market"
    ]
    names = [graph.get_node(i).name for i in comp_ids if graph.get_node(i)]
    feats = set().union(*(
        _targets_for(graph, i, "has_feature") for i in comp_ids
    ))
    techs = set().union(*(
        _targets_for(graph, i, "uses_technology") for i in comp_ids
    ))
    threats = sum(
        1 for i in comp_ids for e in graph.get_edges(i, "out")
        if e.edge_type == "threatens" and e.target_id in comp_ids
    )
    return {
        "segment": seg_nodes[0].name,
        "competitors": len(comp_ids),
        "features_tracked": len(feats),
        "technologies": len(techs),
        "threat_count": threats,
        "top_competitors": sorted(names)[:10],
    }


def _matching_ids(graph: KnowledgeGraphService, node_type: str, query: str) -> set[str]:
    return {n.id for n in _matching_nodes(graph, node_type, query)}


def _matching_nodes(graph: KnowledgeGraphService, node_type: str, query: str) -> list[Node]:
    val = query.lower()
    return [n for n in graph.list_nodes(node_type) if val in n.name.lower() or val == n.id.lower()]


def _targets_for(graph: KnowledgeGraphService, node_id: str, edge_type: str) -> set[str]:
    return {e.target_id for e in graph.get_edges(node_id, "out") if e.edge_type == edge_type}


def _threat_level(have_it: int, total: int) -> str:
    if total == 0:
        return "low"
    ratio = have_it / total
    if ratio > 0.7:
        return "high"
    return "medium" if ratio > 0.3 else "low"


def _recommend(feature: str, have: int, total: int, threat: str) -> str:
    if have == 0:
        return f"No competitor has '{feature}' — potential differentiator"
    suffix = {"high": "Table stakes — must have.", "medium": "Growing trend.",
              "low": "Differentiator opportunity."}[threat]
    return f"{have}/{total} competitors have this. {suffix}"


def _empty_landscape(segment: str) -> dict:
    return {
        "segment": segment, "competitors": 0,
        "features_tracked": 0, "technologies": 0,
        "threat_count": 0, "top_competitors": [],
    }
