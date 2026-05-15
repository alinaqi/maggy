"""Tests for Mnemos v0 backward-compatible APIs."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.mnemos import FatigueTracker, SignalLog


class TestFatigueTracker:
    def test_composite_and_state_ok(self):
        tracker = FatigueTracker()
        tracker.record("context_load", 0.2)
        tracker.record("turn_pressure", 0.1)
        tracker.record("reread_ratio", 0.2)
        tracker.record("handoff_risk", 0.1)
        assert round(tracker.composite(), 2) == 0.15
        assert tracker.state() == "ok"

    def test_rejects_invalid_dimension(self):
        tracker = FatigueTracker()
        with pytest.raises(ValueError, match="Unknown dimension"):
            tracker.record("bogus", 0.5)

    def test_model_switch_increases_reread_ratio(self):
        tracker = FatigueTracker()
        tracker.record("reread_ratio", 0.2)
        tracker.on_model_switch(128_000)
        assert tracker.context_window == 128_000
        assert tracker.dimensions["reread_ratio"] == 0.35

    def test_state_thresholds(self):
        tracker = FatigueTracker()
        for name in tracker.dimensions:
            tracker.record(name, 0.6)
        assert tracker.state() == "compress"
        for name in tracker.dimensions:
            tracker.record(name, 0.9)
        assert tracker.state() == "critical"


class TestSignalLog:
    def test_append_and_recent(self, tmp_path: Path):
        log = SignalLog(tmp_path / "signals.jsonl")
        log.append({"kind": "fatigue", "value": 0.4})
        log.append({"kind": "switch", "value": 1})
        assert log.recent(1) == [{"kind": "switch", "value": 1}]
        assert log.recent(2)[0]["kind"] == "fatigue"
