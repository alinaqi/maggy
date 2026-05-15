"""Tests for mnemos fatigue computation."""

import json
from pathlib import Path

import pytest

from maggy.mnemos.fatigue import (
    compute_fatigue,
    estimate_token_util,
    load_fatigue,
    save_fatigue,
)
from maggy.mnemos.models import FatigueState


class TestTokenUtilEstimate:
    def test_empty_file(self, tmp_path: Path):
        f = tmp_path / "t.jsonl"
        f.write_bytes(b"")
        assert estimate_token_util(f) == 0.0

    def test_half_full(self, tmp_path: Path):
        f = tmp_path / "t.jsonl"
        f.write_bytes(b"x" * 400_000)
        util = estimate_token_util(f)
        assert 0.49 < util < 0.51

    def test_full(self, tmp_path: Path):
        f = tmp_path / "t.jsonl"
        f.write_bytes(b"x" * 800_000)
        util = estimate_token_util(f)
        assert util == pytest.approx(1.0, abs=0.01)

    def test_over_full_capped(self, tmp_path: Path):
        f = tmp_path / "t.jsonl"
        f.write_bytes(b"x" * 1_600_000)
        util = estimate_token_util(f)
        assert util <= 1.0

    def test_missing_file(self, tmp_path: Path):
        f = tmp_path / "nonexistent.jsonl"
        assert estimate_token_util(f) == 0.0


class TestComputeFatigue:
    def test_tier0_formula(self, tmp_path: Path):
        f = tmp_path / "t.jsonl"
        f.write_bytes(b"x" * 400_000)  # 50% util
        fs = compute_fatigue(f)
        # fatigue = 0.40 * 0.5 = 0.20
        assert fs.score == pytest.approx(0.20, abs=0.01)
        assert fs.state == "FLOW"

    def test_high_fatigue(self, tmp_path: Path):
        f = tmp_path / "t.jsonl"
        f.write_bytes(b"x" * 800_000)  # 100% util
        fs = compute_fatigue(f)
        # fatigue = 0.40 * 1.0 = 0.40
        assert fs.score == pytest.approx(0.40, abs=0.01)
        assert fs.state == "COMPRESS"


class TestFatiguePersistence:
    def test_save_and_load(self, tmp_mnemos_dir: Path):
        fs = FatigueState(score=0.55, token_util=0.9)
        save_fatigue(tmp_mnemos_dir, fs)
        loaded = load_fatigue(tmp_mnemos_dir)
        assert loaded is not None
        assert loaded.score == pytest.approx(0.55)

    def test_load_missing(self, tmp_mnemos_dir: Path):
        assert load_fatigue(tmp_mnemos_dir) is None
