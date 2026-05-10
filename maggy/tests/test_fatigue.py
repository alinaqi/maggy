"""Tests for fatigue tracking — profiles and model comparison."""

from __future__ import annotations

from maggy.fatigue import (
    FatigueProfile,
    MODEL_CONTEXT_WINDOWS,
    compare_fatigue,
    create_profile,
)


class TestFatigueProfile:
    def test_zero_usage_no_fatigue(self):
        p = FatigueProfile(model="claude", context_window=200_000)
        assert p.fatigue_score == 0.0
        assert p.raw_utilization == 0.0

    def test_full_context_high_fatigue(self):
        p = FatigueProfile(
            model="claude", context_window=200_000,
            tokens_used=200_000, turns=50,
        )
        assert p.fatigue_score == 1.0

    def test_half_context_moderate_fatigue(self):
        p = FatigueProfile(
            model="gpt", context_window=128_000,
            tokens_used=64_000, turns=10,
        )
        score = p.fatigue_score
        assert 0.3 < score < 0.6

    def test_zero_context_window_safe(self):
        p = FatigueProfile(model="x", context_window=0)
        assert p.raw_utilization == 0.0


class TestShouldCheckpoint:
    def test_below_threshold(self):
        p = FatigueProfile(
            model="claude", context_window=200_000,
            tokens_used=50_000,
        )
        assert not p.should_checkpoint()

    def test_above_threshold(self):
        p = FatigueProfile(
            model="claude", context_window=200_000,
            tokens_used=180_000, turns=40,
        )
        assert p.should_checkpoint()

    def test_custom_threshold(self):
        p = FatigueProfile(
            model="claude", context_window=200_000,
            tokens_used=100_000,
        )
        assert p.should_checkpoint(threshold=0.3)


class TestCreateProfile:
    def test_known_model(self):
        p = create_profile("claude")
        assert p.context_window == 200_000

    def test_unknown_model_defaults(self):
        p = create_profile("unknown-model")
        assert p.context_window == 128_000


class TestCompareFatigue:
    def test_sorted_by_fatigue(self):
        p1 = FatigueProfile(
            model="claude", context_window=200_000,
            tokens_used=180_000, turns=40,
        )
        p2 = FatigueProfile(
            model="gpt", context_window=128_000,
            tokens_used=10_000, turns=2,
        )
        result = compare_fatigue([p1, p2])
        assert result[0]["model"] == "claude"
        assert result[0]["fatigue"] > result[1]["fatigue"]
