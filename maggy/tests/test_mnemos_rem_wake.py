"""Tests for REM Phase 4: Wake State Reconstruction."""

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import MnemoNode
from maggy.mnemos.rem_wake import (
    build_wake_summary,
    count_active_nodes,
    run_wake_reconstruction,
    select_wake_context,
)


def _node(weight: float = 1.0) -> MnemoNode:
    return MnemoNode(
        type="FactNode", task_id="t1",
        content="test", activation_weight=weight,
    )


class TestCountActiveNodes:
    def test_counts_only_active(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        db.insert_node(_node())
        n2 = MnemoNode(
            type="FactNode", task_id="t1",
            content="x", status="COMPRESSED",
        )
        db.insert_node(n2)
        assert count_active_nodes(db) == 1


class TestSelectWakeContext:
    def test_targets_50_percent(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        for _ in range(10):
            db.insert_node(_node())
        wake = select_wake_context(db, 10)
        assert len(wake) == 5  # 50% of 10

    def test_minimum_one(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        db.insert_node(_node())
        wake = select_wake_context(db, 1)
        assert len(wake) >= 1


class TestBuildWakeSummary:
    def test_format(self):
        nodes = [_node()]
        summary = build_wake_summary(nodes)
        assert "Wake context:" in summary
        assert "FactNode" in summary


class TestRunWakeReconstruction:
    def test_full_phase(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        for _ in range(6):
            db.insert_node(_node())
        stats = run_wake_reconstruction(db, 6)
        assert stats["wake_nodes"] == 3
        assert stats["ratio"] == 0.5
