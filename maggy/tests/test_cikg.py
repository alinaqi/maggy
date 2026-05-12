"""Tests for CIKG — knowledge graph, queries, market scoring."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.cikg.graph import KnowledgeGraphService
from maggy.cikg.models import Edge, Node
from maggy.cikg.queries import (
    compare_entities,
    find_gaps,
    find_gaps_raw,
    get_landscape,
    get_segment_landscape,
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


class TestServiceQueries:
    def _seed_graph(self, tmp_path: Path) -> KnowledgeGraphService:
        g = KnowledgeGraphService(tmp_path / "cikg.db")
        g.add_node(Node(id="c0", node_type="competitor", name="Alpha"))
        g.add_node(Node(id="c1", node_type="competitor", name="Bravo"))
        g.add_node(Node(id="c2", node_type="competitor", name="Charlie"))
        g.add_node(Node(id="f1", node_type="feature", name="SSO"))
        g.add_node(Node(id="f2", node_type="feature", name="AI Chat"))
        g.add_node(Node(id="t1", node_type="technology", name="React"))
        g.add_node(Node(id="s1", node_type="market_segment", name="SMB"))
        g.add_node(Node(id="s2", node_type="market_segment", name="Enterprise"))
        g.add_edge(Edge("c0", "f1", "has_feature"))
        g.add_edge(Edge("c1", "f1", "has_feature"))
        g.add_edge(Edge("c1", "f2", "has_feature"))
        g.add_edge(Edge("c0", "c1", "competes_with"))
        g.add_edge(Edge("c0", "t1", "uses_technology"))
        g.add_edge(Edge("c1", "t1", "uses_technology"))
        g.add_edge(Edge("c0", "s1", "targets_market"))
        g.add_edge(Edge("c1", "s1", "targets_market"))
        g.add_edge(Edge("c2", "s2", "targets_market"))
        g.add_edge(Edge("c1", "c0", "threatens"))
        return g

    def test_find_gaps_raw(self, tmp_path: Path):
        g = self._seed_graph(tmp_path)
        result = find_gaps_raw(g, "SSO")
        assert {item["entity"] for item in result} == {
            "Alpha", "Bravo", "Charlie",
        }
        status = {item["entity"]: item["status"] for item in result}
        assert status == {
            "Alpha": "has",
            "Bravo": "has",
            "Charlie": "lacks",
        }

    def test_compare_entities(self, tmp_path: Path):
        g = self._seed_graph(tmp_path)
        result = compare_entities(g, "c0", "c1")
        assert result["shared"] == ["f1"]
        assert result["only_a"] == []
        assert result["only_b"] == ["f2"]
        assert result["relationships"][0]["edge_type"] == "competes_with"

    def test_segment_landscape(self, tmp_path: Path):
        g = self._seed_graph(tmp_path)
        result = get_segment_landscape(g, "SMB")
        assert result["segment"] == "SMB"
        assert result["competitors"] == 2
        assert result["features_tracked"] == 2
        assert result["technologies"] == 1
        assert result["threat_count"] == 1


class TestTypeValidation:
    def test_valid_node_type_accepted(self):
        node = Node(id="c1", node_type="competitor", name="Test")
        assert node.node_type == "competitor"

    def test_invalid_node_type_rejected(self):
        with pytest.raises(ValueError, match="Invalid node_type"):
            Node(id="c1", node_type="bogus", name="Test")

    def test_valid_edge_type_accepted(self):
        edge = Edge(source_id="a", target_id="b", edge_type="has_feature")
        assert edge.edge_type == "has_feature"

    def test_invalid_edge_type_rejected(self):
        with pytest.raises(ValueError, match="Invalid edge_type"):
            Edge(source_id="a", target_id="b", edge_type="bogus")
