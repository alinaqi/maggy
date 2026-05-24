"""Tests for Plane 3 — Integrity (IF-3 to IF-8 checks → F3)."""

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
_load("cortex_reader", "cortex_reader.py")
_integrity = _load("telos_integrity", "plane_integrity.py")
compute_f3 = _integrity.compute_f3
IntentNode = sys.modules["telos_models"].IntentNode


def _node(**kw):
    defaults = {
        "id": "R-1", "goal": "g", "owner": "o",
        "status": "proposed", "created_at": "2026-01-01",
    }
    defaults.update(kw)
    return IntentNode.from_dict(defaults)


class TestOrphanCheck:
    """IF-3: symbols with no reason edges."""

    def test_no_orphans_clean(self):
        result = compute_f3(
            reasons=[_node(preconditions='["x"]')],
            orphans=[],
            stale=[],
        )
        assert result["f3"] == pytest.approx(1.0)

    def test_orphans_reduce_score(self):
        result = compute_f3(
            reasons=[_node()],
            orphans=[{"name": "fn_x"}, {"name": "fn_y"}],
            stale=[],
        )
        assert result["f3"] < 1.0
        assert "orphan" in result["violations"][0].lower()


class TestEmptyContracts:
    """IF-4: reasons with empty pre/post/invariants."""

    def test_no_contracts_flagged(self):
        node = _node(id="R-10")
        result = compute_f3(
            reasons=[node],
            orphans=[],
            stale=[],
        )
        assert any(
            "contract" in v.lower()
            for v in result["violations"]
        )

    def test_with_contracts_clean(self):
        node = _node(
            id="R-11",
            preconditions='["db up"]',
        )
        result = compute_f3(
            reasons=[node],
            orphans=[],
            stale=[],
        )
        contract_violations = [
            v for v in result["violations"]
            if "contract" in v.lower()
        ]
        assert len(contract_violations) == 0


class TestStaleReasons:
    """IF-6: proposed > N days, never fulfilled."""

    def test_stale_reduces_score(self):
        stale = _node(id="R-20")
        result = compute_f3(
            reasons=[stale],
            orphans=[],
            stale=[stale],
        )
        assert result["f3"] < 1.0
        assert any(
            "stale" in v.lower()
            for v in result["violations"]
        )


class TestScopeSprawl:
    """IF-7: reasons scoping > 10 files."""

    def test_sprawl_flagged(self):
        import json
        files = [f"f{i}.py" for i in range(15)]
        node = _node(
            id="R-30",
            scope=json.dumps(files),
            preconditions='["x"]',
        )
        result = compute_f3(
            reasons=[node],
            orphans=[],
            stale=[],
        )
        assert any(
            "sprawl" in v.lower()
            for v in result["violations"]
        )

    def test_narrow_scope_clean(self):
        node = _node(
            id="R-31",
            scope='["a.py", "b.py"]',
            preconditions='["x"]',
        )
        result = compute_f3(
            reasons=[node],
            orphans=[],
            stale=[],
        )
        sprawl = [
            v for v in result["violations"]
            if "sprawl" in v.lower()
        ]
        assert len(sprawl) == 0


class TestF3Score:

    def test_perfect_score(self):
        node = _node(preconditions='["x"]')
        result = compute_f3(
            reasons=[node],
            orphans=[],
            stale=[],
        )
        assert result["f3"] == pytest.approx(1.0)

    def test_floor_at_zero(self):
        nodes = [_node(id=f"R-{i}") for i in range(20)]
        orphans = [{"name": f"o{i}"} for i in range(30)]
        result = compute_f3(
            reasons=nodes,
            orphans=orphans,
            stale=nodes,
        )
        assert result["f3"] >= 0.0
