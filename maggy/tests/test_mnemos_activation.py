"""Tests for activation weight computation."""

from datetime import datetime, timedelta, timezone

from maggy.mnemos.activation import (
    compute_activation_weight,
    compute_centrality_score,
    compute_frequency_score,
    compute_recency_score,
)
from maggy.mnemos.models import MnemoNode, NodeLink


def _node(
    access_count: int = 0,
    last_accessed: datetime | None = None,
) -> MnemoNode:
    la = last_accessed or datetime.now(timezone.utc)
    return MnemoNode(
        type="FactNode",
        task_id="t1",
        content="test",
        access_count=access_count,
        last_accessed=la,
    )


class TestRecencyScore:
    def test_recent_node_high_score(self):
        n = _node()
        assert compute_recency_score(n) > 0.9

    def test_old_node_decays(self):
        old = datetime.now(timezone.utc) - timedelta(hours=5)
        n = _node(last_accessed=old)
        assert compute_recency_score(n) < 0.1


class TestFrequencyScore:
    def test_zero_access(self):
        assert compute_frequency_score(_node(access_count=0)) == 0.0

    def test_high_access(self):
        s = compute_frequency_score(_node(access_count=100))
        assert 0.5 < s <= 1.0

    def test_capped_at_one(self):
        s = compute_frequency_score(_node(access_count=10000))
        assert s <= 1.0


class TestCentralityScore:
    def test_no_links(self):
        assert compute_centrality_score("n1", []) == 0.0

    def test_fully_connected(self):
        links = [NodeLink(source_id="n1", target_id="n2")]
        assert compute_centrality_score("n1", links) == 1.0

    def test_not_connected(self):
        links = [NodeLink(source_id="n2", target_id="n3")]
        assert compute_centrality_score("n1", links) == 0.0


class TestCompositeWeight:
    def test_recent_frequent_node(self):
        n = _node(access_count=50)
        links = [NodeLink(source_id=n.id, target_id="x")]
        w = compute_activation_weight(n, links)
        assert 0.0 < w <= 1.0

    def test_cold_node_low_weight(self):
        old = datetime.now(timezone.utc) - timedelta(hours=10)
        n = _node(last_accessed=old)
        w = compute_activation_weight(n, [])
        assert w < 0.1
