"""Tests for advanced DB queries."""

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.db_queries import (
    bulk_update_status,
    list_nodes_below_weight,
    update_node_fingerprint,
    update_node_status,
    update_node_summary,
    update_node_weight,
)
from maggy.mnemos.models import MnemoNode


def _node(
    weight: float = 1.0,
    ntype: str = "FactNode",
) -> MnemoNode:
    return MnemoNode(
        type=ntype,
        task_id="t1",
        content="test",
        activation_weight=weight,
    )


class TestUpdateNodeStatus:
    def test_changes_status(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n = _node()
        db.insert_node(n)
        update_node_status(db.conn, n.id, "COMPRESSED")
        refreshed = db.get_node(n.id)
        assert refreshed.status == "COMPRESSED"


class TestUpdateNodeWeight:
    def test_changes_weight(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n = _node(weight=1.0)
        db.insert_node(n)
        update_node_weight(db.conn, n.id, 0.5)
        refreshed = db.get_node(n.id)
        assert abs(refreshed.activation_weight - 0.5) < 0.01


class TestUpdateNodeSummary:
    def test_sets_summary(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n = _node()
        db.insert_node(n)
        update_node_summary(db.conn, n.id, "compressed")
        refreshed = db.get_node(n.id)
        assert refreshed.summary == "compressed"


class TestListNodesBelowWeight:
    def test_filters_by_threshold(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n1 = _node(weight=0.1)
        n2 = _node(weight=0.5)
        db.insert_node(n1)
        db.insert_node(n2)
        below = list_nodes_below_weight(db.conn, 0.3)
        assert len(below) == 1
        assert below[0].id == n1.id

    def test_filters_by_type(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n1 = _node(weight=0.1, ntype="FactNode")
        n2 = _node(weight=0.1, ntype="ContextNode")
        db.insert_node(n1)
        db.insert_node(n2)
        result = list_nodes_below_weight(
            db.conn, 0.3, node_type="ContextNode",
        )
        assert len(result) == 1


class TestBulkUpdateStatus:
    def test_updates_multiple(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        nodes = [_node() for _ in range(3)]
        for n in nodes:
            db.insert_node(n)
        ids = [n.id for n in nodes]
        count = bulk_update_status(db.conn, ids, "EVICTED")
        assert count == 3

    def test_empty_list(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        assert bulk_update_status(db.conn, [], "EVICTED") == 0


class TestUpdateFingerprint:
    def test_sets_fingerprint(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n = _node()
        db.insert_node(n)
        update_node_fingerprint(db.conn, n.id, "abc|def|ghi")
        refreshed = db.get_node(n.id)
        assert refreshed.fingerprint == "abc|def|ghi"
