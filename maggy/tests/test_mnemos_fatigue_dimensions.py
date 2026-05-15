"""Tests for 4-dimension fatigue computation."""

from datetime import datetime, timezone
from pathlib import Path

from maggy.mnemos.fatigue import compute_fatigue
from maggy.mnemos.fatigue_dimensions import (
    composite_fatigue,
    compute_all_dimensions,
    compute_error_density,
    compute_reread_ratio,
    compute_scope_scatter,
)
from maggy.mnemos.signals import ToolSignal


def _sig(
    tool: str = "Read",
    path: str = "src/a.py",
    outcome: str = "success",
) -> ToolSignal:
    return ToolSignal(
        timestamp=datetime.now(timezone.utc).isoformat(),
        tool_name=tool,
        file_path=path,
        outcome=outcome,
    )


class TestScopeScatter:
    def test_single_dir(self):
        sigs = [_sig(path="src/a.py"), _sig(path="src/b.py")]
        assert compute_scope_scatter(sigs) < 0.6

    def test_many_dirs(self):
        sigs = [_sig(path=f"d{i}/f.py") for i in range(10)]
        assert compute_scope_scatter(sigs) == 1.0

    def test_empty(self):
        assert compute_scope_scatter([]) == 0.0


class TestRereadRatio:
    def test_no_rereads(self):
        sigs = [_sig(path="a.py"), _sig(path="b.py")]
        assert compute_reread_ratio(sigs) == 0.0

    def test_all_rereads(self):
        sigs = [_sig(path="a.py")] * 4
        assert compute_reread_ratio(sigs) == 0.75

    def test_no_reads(self):
        sigs = [_sig(tool="Write")]
        assert compute_reread_ratio(sigs) == 0.0


class TestErrorDensity:
    def test_no_errors(self):
        sigs = [_sig(outcome="success")]
        assert compute_error_density(sigs) == 0.0

    def test_all_errors(self):
        sigs = [_sig(outcome="error")] * 3
        assert compute_error_density(sigs) == 1.0

    def test_empty(self):
        assert compute_error_density([]) == 0.0


class TestCompositeFatigue:
    def test_all_zero(self):
        dims = {
            "token_util": 0,
            "scope_scatter": 0,
            "reread_ratio": 0,
            "error_density": 0,
        }
        assert composite_fatigue(dims) == 0.0

    def test_all_max(self):
        dims = {
            "token_util": 1.0,
            "scope_scatter": 1.0,
            "reread_ratio": 1.0,
            "error_density": 1.0,
        }
        assert composite_fatigue(dims) == 1.0


class TestFatigueBackwardCompat:
    def test_no_signals_tier0(self, tmp_path):
        t = tmp_path / "t.jsonl"
        t.write_bytes(b"x" * 400_000)
        fs = compute_fatigue(t)
        assert fs.scope_scatter == 0.0

    def test_with_signals_full(self, tmp_path):
        t = tmp_path / "t.jsonl"
        t.write_bytes(b"x" * 400_000)
        sigs = [_sig(outcome="error")] * 5
        fs = compute_fatigue(t, signals=sigs)
        assert fs.error_density > 0
