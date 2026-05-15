"""Tests for reward table."""

import pytest
from pathlib import Path

from maggy.scores import RewardTable
from maggy.config import MaggyConfig, StorageConfig


@pytest.fixture
def table(tmp_path: Path) -> RewardTable:
    cfg = MaggyConfig(
        storage=StorageConfig(path=str(tmp_path / "maggy.db")),
    )
    return RewardTable(cfg)


class TestRewardTable:
    def test_record_and_heatmap(self, table):
        table.record("claude", "bugfix", "high", 0.9)
        hm = table.heatmap()
        assert len(hm) == 1
        assert hm[0]["model"] == "claude"
        assert hm[0]["avg_reward"] == 0.9

    def test_multiple_records(self, table):
        table.record("claude", "bugfix", "high", 0.8)
        table.record("claude", "bugfix", "high", 1.0)
        hm = table.heatmap()
        assert hm[0]["avg_reward"] == 0.9
        assert hm[0]["samples"] == 2

    def test_best_model_needs_min_samples(self, table):
        table.record("claude", "bugfix", "high", 0.9)
        # Only 1 sample — below MIN_SAMPLES
        assert table.best_model("bugfix", "high") is None

    def test_best_model_with_enough_samples(self, table):
        for _ in range(6):
            table.record("claude", "bugfix", "high", 0.9)
        for _ in range(6):
            table.record("kimi", "bugfix", "high", 0.5)
        best = table.best_model("bugfix", "high")
        assert best == "claude"

    def test_no_data(self, table):
        assert table.best_model("docs", "low") is None

    def test_heatmap_groups_correctly(self, table):
        table.record("claude", "bugfix", "high", 0.9)
        table.record("kimi", "docs", "low", 0.7)
        hm = table.heatmap()
        assert len(hm) == 2

    def test_empty_heatmap(self, table):
        assert table.heatmap() == []
