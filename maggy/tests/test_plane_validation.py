"""Tests for Plane 2 — Validation (F2 from Cortex drift_events)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_TELOS_DIR = (
    Path(__file__).resolve().parent.parent / "plugins" / "telos"
)


def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    path = _TELOS_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_load("telos_models", "models.py")
_validation = _load("telos_validation", "plane_validation.py")
compute_f2 = _validation.compute_f2


class TestComputeF2:

    def test_no_drift_returns_one(self):
        reasons = [{"id": "R-1"}, {"id": "R-2"}]
        drift = []
        assert compute_f2(drift, reasons) == pytest.approx(1.0)

    def test_no_reasons_returns_one(self):
        assert compute_f2([], []) == pytest.approx(1.0)

    def test_single_drift_moderate(self):
        reasons = [{"id": "R-1"}]
        drift = [
            {"from_reason_id": "R-1", "severity": 0.6},
        ]
        assert compute_f2(drift, reasons) == pytest.approx(0.4)

    def test_per_reason_severity_capped(self):
        """Multiple drifts on same reason capped at 1.0."""
        reasons = [{"id": "R-1"}]
        drift = [
            {"from_reason_id": "R-1", "severity": 0.8},
            {"from_reason_id": "R-1", "severity": 0.7},
        ]
        f2 = compute_f2(drift, reasons)
        assert f2 == pytest.approx(0.0)

    def test_multi_reason_spread(self):
        reasons = [{"id": "R-1"}, {"id": "R-2"}]
        drift = [
            {"from_reason_id": "R-1", "severity": 0.4},
            {"from_reason_id": "R-2", "severity": 0.2},
        ]
        expected = 1 - (0.4 + 0.2) / 2
        assert compute_f2(drift, reasons) == pytest.approx(
            expected,
        )

    def test_floor_at_zero(self):
        reasons = [{"id": "R-1"}]
        drift = [
            {"from_reason_id": "R-1", "severity": 1.5},
        ]
        assert compute_f2(drift, reasons) == pytest.approx(0.0)
