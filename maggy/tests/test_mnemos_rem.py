"""Tests for REM process orchestrator."""

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import MnemoNode
from maggy.mnemos.rem import (
    format_rem_report,
    run_rem_cycle,
    should_trigger_rem,
)


class TestShouldTriggerRem:
    def test_above_threshold(self):
        assert should_trigger_rem(0.80) is True

    def test_at_threshold(self):
        assert should_trigger_rem(0.75) is True

    def test_below_threshold(self):
        assert should_trigger_rem(0.50) is False


class TestRunRemCycle:
    def test_full_cycle_empty(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        stats = run_rem_cycle(db, tmp_mnemos_dir)
        assert "slow_wave" in stats
        assert "skills" in stats
        assert "pruning" in stats
        assert "wake" in stats

    def test_with_nodes(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        for i in range(5):
            db.insert_node(MnemoNode(
                type="ResultNode", task_id="t1",
                content=f"r{i}",
            ))
        stats = run_rem_cycle(db, tmp_mnemos_dir)
        assert stats["slow_wave"]["compressed"] >= 1


class TestFormatRemReport:
    def test_format(self):
        stats = {
            "slow_wave": {"compressed": 5, "evicted": 2},
            "skills": {"promoted": 1},
            "pruning": {"crystallized_tasks": 0},
            "wake": {"wake_nodes": 3, "ratio": 0.5},
        }
        report = format_rem_report(stats)
        assert "REM CYCLE" in report
        assert "5 compressed" in report
