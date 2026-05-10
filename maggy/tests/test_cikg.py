"""Tests for CIKG — knowledge graph, queries, market scoring."""

from __future__ import annotations

from pathlib import Path

from maggy.cikg.graph import KnowledgeGraphService
from maggy.cikg.models import Edge, MarketScore, Node
from maggy.cikg.queries import (
    compare_entities,
    find_gaps,
    get_landscape,
)


class TestKnowledgeGraph:
    def test_add_and_get_node(self, tmp_path: Path):
        g = KnowledgeGraphService(tmp_path / "cikg.db")
        node = Node(
            id="c1", node_type="competitor", name="Acme",
        )
        g.add_node(node)
        result = g.get_node("c1")
        assert result is not None
        assert result.name == "Acme"

    def test_get_missing_node(self, tmp_path: Path):
        g = KnowledgeGraphService(tmp_path / "cikg.db")
        assert g.get_node("nonexistent") is None

    def test_list_nodes_by_type(self, tmp_path: Path):
        g = KnowledgeGraphService(tmp_path / "cikg.db")
        g.add_node(Node(id="c1", node_type="competitor", name="A"))
        g.add_node(Node(id="f1", node_type="feature", name="B"))
        comps = g.list_nodes("competitor")
        assert len(comps) == 1
        assert comps[0].name == "A"

    def test_list_all_nodes(self, tmp_path: Path):
        g = KnowledgeGraphService(tmp_path / "cikg.db")
        g.add_node(Node(id="c1", node_type="competitor", name="A"))
        g.add_node(Node(id="f1", node_type="feature", name="B"))
        assert len(g.list_nodes()) == 2


class TestEdges:
    def test_add_and_get_edge(self, tmp_path: Path):
        g = KnowledgeGraphService(tmp_path / "cikg.db")
        g.add_node(Node(id="c1", node_type="competitor", name="A"))
        g.add_node(Node(id="f1", node_type="feature", name="SSO"))
        g.add_edge(Edge(
            source_id="c1", target_id="f1",
            edge_type="has_feature",
        ))
        edges = g.get_edges("c1", "out")
        assert len(edges) == 1
        assert edges[0].target_id == "f1"

    def test_inbound_edges(self, tmp_path: Path):
        g = KnowledgeGraphService(tmp_path / "cikg.db")
        g.add_node(Node(id="c1", node_type="competitor", name="A"))
        g.add_node(Node(id="f1", node_type="feature", name="SSO"))
        g.add_edge(Edge(
            source_id="c1", target_id="f1",
            edge_type="has_feature",
        ))
        edges = g.get_edges("f1", "in")
        assert len(edges) == 1
        assert edges[0].source_id == "c1"

    def test_neighbors(self, tmp_path: Path):
        g = KnowledgeGraphService(tmp_path / "cikg.db")
        g.add_node(Node(id="c1", node_type="competitor", name="A"))
        g.add_node(Node(id="f1", node_type="feature", name="SSO"))
        g.add_edge(Edge(
            source_id="c1", target_id="f1",
            edge_type="has_feature",
        ))
        neighbors = g.neighbors("c1")
        assert len(neighbors) == 1
        assert neighbors[0].id == "f1"


class TestDeleteNode:
    def test_delete_removes_node_and_edges(self, tmp_path: Path):
        g = KnowledgeGraphService(tmp_path / "cikg.db")
        g.add_node(Node(id="c1", node_type="competitor", name="A"))
        g.add_node(Node(id="f1", node_type="feature", name="SSO"))
        g.add_edge(Edge(
            source_id="c1", target_id="f1",
            edge_type="has_feature",
        ))
        g.delete_node("c1")
        assert g.get_node("c1") is None
        assert g.get_edges("c1", "out") == []


class TestQueries:
    def _seed_graph(self, tmp_path: Path) -> KnowledgeGraphService:
        g = KnowledgeGraphService(tmp_path / "cikg.db")
        for i in range(3):
            g.add_node(Node(
                id=f"c{i}", node_type="competitor",
                name=f"Comp{i}",
            ))
        g.add_node(Node(
            id="f1", node_type="feature", name="SSO",
        ))
        g.add_node(Node(
            id="t1", node_type="technology", name="React",
        ))
        # 2 out of 3 competitors have SSO
        g.add_edge(Edge("c0", "f1", "has_feature"))
        g.add_edge(Edge("c1", "f1", "has_feature"))
        return g

    def test_find_gaps_existing(self, tmp_path: Path):
        g = self._seed_graph(tmp_path)
        score = find_gaps(g, "SSO")
        assert score.feature == "SSO"
        assert score.gap_count == 1
        assert score.threat_level == "medium"

    def test_find_gaps_unknown(self, tmp_path: Path):
        g = self._seed_graph(tmp_path)
        score = find_gaps(g, "AI Chat")
        assert score.gap_count == 3
        assert score.threat_level == "low"
        assert "differentiator" in score.recommendation.lower()

    def test_get_landscape(self, tmp_path: Path):
        g = self._seed_graph(tmp_path)
        ls = get_landscape(g)
        assert ls["competitors"] == 3
        assert ls["features_tracked"] == 1
        assert ls["technologies"] == 1

    def test_compare_entities(self, tmp_path: Path):
        g = self._seed_graph(tmp_path)
        result = compare_entities(g, "c0", "c1")
        assert "f1" in result["shared"]
