"""Tests for REM Phase 1: Slow-Wave."""

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.db_queries import update_node_weight
from maggy.mnemos.models import MnemoNode
from maggy.mnemos.rem_slow_wave import (
    batch_compress,
    evict_cold_context_nodes,
    run_slow_wave,
    select_result_nodes,
)


def _result(i: int = 0) -> MnemoNode:
    return MnemoNode(
        type="ResultNode", task_id="t1", content=f"r{i}",
    )


def _context(weight: float = 0.05) -> MnemoNode:
    return MnemoNode(
        type="ContextNode", task_id="t1",
        content="ctx", activation_weight=weight,
    )


class TestSelectResultNodes:
    def test_only_active(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n = _result()
        db.insert_node(n)
        result = select_result_nodes(db)
        assert len(result) == 1

    def test_excludes_compressed(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n = MnemoNode(
            type="ResultNode", task_id="t1",
            content="r", status="COMPRESSED",
        )
        db.insert_node(n)
        assert select_result_nodes(db) == []


class TestBatchCompress:
    def test_compresses_all(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        nodes = [_result(i) for i in range(5)]
        for n in nodes:
            db.insert_node(n)
        count = batch_compress(db, nodes, batch_size=3)
        assert count == 5


class TestEvictColdContextNodes:
    def test_evicts_low_weight(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n = _context(weight=0.05)
        db.insert_node(n)
        update_node_weight(db.conn, n.id, 0.05)
        evicted = evict_cold_context_nodes(db)
        assert evicted == 1


class TestRunSlowWave:
    def test_full_phase(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        db.insert_node(_result())
        stats = run_slow_wave(db)
        assert stats["compressed"] >= 1
