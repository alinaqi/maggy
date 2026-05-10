"""Integration test: CI fail -> Signal -> Pattern -> Fix.

Tests the process intelligence pipeline with CIKG and Engram.
"""

from __future__ import annotations

from pathlib import Path

from maggy.cikg.graph import KnowledgeGraphService
from maggy.cikg.models import Edge, Node
from maggy.cikg.queries import find_gaps, get_landscape
from maggy.engram.diagnostics import diagnose
from maggy.engram.record import EngramRecord
from maggy.engram.retrieval import EngramRetrieval
from maggy.engram.store import EngramStore
from maggy.lexon.router import LexonRouter


class TestProcessLoop:
    def test_cikg_gap_to_engram(self, tmp_path: Path):
        """Detect feature gap in CIKG, store in Engram."""
        # 1. Build competitive landscape
        g = KnowledgeGraphService(tmp_path / "cikg.db")
        for i in range(3):
            g.add_node(Node(
                id=f"c{i}", node_type="competitor",
                name=f"Competitor{i}",
            ))
        g.add_node(Node(
            id="f1", node_type="feature", name="SSO",
        ))
        g.add_edge(Edge("c0", "f1", "has_feature"))

        # 2. Detect gap
        score = find_gaps(g, "SSO")
        assert score.gap_count == 2

        # 3. Store insight in Engram
        store = EngramStore(tmp_path / "engram.db")
        store.write(EngramRecord(
            engram_id="gap-sso",
            namespace="process",
            memory_type="decision",
            content=f"Gap detected: {score.recommendation}",
            tags=["cikg", "gap", "sso"],
        ))

        # 4. Verify retrieval
        retrieval = EngramRetrieval(store)
        results = retrieval.by_tag("cikg")
        assert len(results) == 1
        assert "Gap detected" in results[0].content

    def test_lexon_to_engram(self, tmp_path: Path):
        """Parse intent with Lexon, store in Engram."""
        # 1. Parse user intent
        router = LexonRouter()
        record = router.route("deploy the app to production")
        assert record.confidence > 0.5

        # 2. Store the resolution in Engram
        store = EngramStore(tmp_path / "engram.db")
        store.write(EngramRecord(
            engram_id="intent-deploy",
            namespace="session-1",
            memory_type="fact",
            content=f"User said '{record.phrase}' -> "
                    f"{record.resolved_tool}",
            tags=["lexon", "intent"],
        ))

        # 3. Verify
        result = store.get("intent-deploy")
        assert result is not None
        assert "deploy" in result.content

    def test_full_diagnostics(self, tmp_path: Path):
        """Memory diagnostics across diverse types."""
        store = EngramStore(tmp_path / "engram.db")
        types = ["fact", "decision", "code_ref", "handoff"]
        for i, mt in enumerate(types):
            store.write(EngramRecord(
                engram_id=f"e{i}",
                namespace="test",
                memory_type=mt,
                content=f"Content for {mt}",
            ))

        profile = diagnose(store)
        assert profile.total_memories == 4
        assert profile.health_score > 0.8
