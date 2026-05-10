"""Tests for RewardTable — record, query, best_model, heatmap."""

from __future__ import annotations

from maggy.scores import MIN_SAMPLES, RewardTable


class TestRewardRecord:
    def test_record_and_heatmap(self, mock_cfg):
        rt = RewardTable(mock_cfg)
        rt.record("claude", "bug", "high", 0.9)
        hm = rt.heatmap()
        assert len(hm) == 1
        assert hm[0]["model"] == "claude"

    def test_multiple_records(self, mock_cfg):
        rt = RewardTable(mock_cfg)
        rt.record("claude", "bug", "high", 0.9)
        rt.record("gpt", "bug", "high", 0.7)
        hm = rt.heatmap()
        assert len(hm) == 2


class TestBestModel:
    def test_no_data_returns_none(self, mock_cfg):
        rt = RewardTable(mock_cfg)
        assert rt.best_model("bug", "high") is None

    def test_insufficient_samples_returns_none(self, mock_cfg):
        rt = RewardTable(mock_cfg)
        for _ in range(MIN_SAMPLES - 1):
            rt.record("claude", "bug", "high", 0.9)
        assert rt.best_model("bug", "high") is None

    def test_sufficient_samples_returns_best(self, mock_cfg):
        rt = RewardTable(mock_cfg)
        for _ in range(MIN_SAMPLES):
            rt.record("claude", "bug", "high", 0.9)
        for _ in range(MIN_SAMPLES):
            rt.record("gpt", "bug", "high", 0.5)
        best = rt.best_model("bug", "high")
        assert best == "claude"


class TestHeatmap:
    def test_empty_heatmap(self, mock_cfg):
        rt = RewardTable(mock_cfg)
        assert rt.heatmap() == []

    def test_heatmap_groups_correctly(self, mock_cfg):
        rt = RewardTable(mock_cfg)
        rt.record("claude", "bug", "high", 0.9)
        rt.record("claude", "feature", "low", 0.8)
        hm = rt.heatmap()
        assert len(hm) == 2
