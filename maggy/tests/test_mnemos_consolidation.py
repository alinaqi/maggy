"""Tests for micro-consolidation."""

from maggy.mnemos.consolidation import (
    compress_nodes,
    evict_nodes,
    run_micro_consolidation,
    select_compress_candidates,
    select_evict_candidates,
    should_consolidate,
)
from maggy.mnemos.db import MnemosDB
from maggy.mnemos.db_queries import update_node_weight
from maggy.mnemos.models import MnemoNode


def _result_node(i: int = 0) -> MnemoNode:
    return MnemoNode(
        type="ResultNode",
        task_id="t1",
        content=f"result {i}",
    )


def _context_node() -> MnemoNode:
    return MnemoNode(
        type="ContextNode",
        task_id="t1",
        content="context data",
        activation_weight=0.05,
    )


class TestShouldConsolidate:
    def test_in_range(self):
        assert should_consolidate(0.50) is True

    def test_below_range(self):
        assert should_consolidate(0.30) is False

    def test_above_range(self):
        assert should_consolidate(0.70) is False

    def test_at_boundary(self):
        assert should_consolidate(0.40) is True


class TestCompression:
    def test_select_candidates(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        for i in range(3):
            db.insert_node(_result_node(i))
        cands = select_compress_candidates(db)
        assert len(cands) == 3

    def test_compress_marks_status(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        nodes = [_result_node(i) for i in range(2)]
        for n in nodes:
            db.insert_node(n)
        compress_nodes(db, nodes)
        for n in nodes:
            refreshed = db.get_node(n.id)
            assert refreshed.status == "COMPRESSED"


class TestEviction:
    def test_evict_low_weight(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n = _context_node()
        db.insert_node(n)
        update_node_weight(db.conn, n.id, 0.05)
        cands = select_evict_candidates(db)
        assert len(cands) == 1
        evicted = evict_nodes(db, cands)
        assert evicted == 1


class TestRunMicroConsolidation:
    def test_no_op_below_range(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        result = run_micro_consolidation(db, 0.20)
        assert result["compressed"] == 0

    def test_runs_in_range(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        for i in range(3):
            db.insert_node(_result_node(i))
        result = run_micro_consolidation(db, 0.50)
        assert result["compressed"] == 3
