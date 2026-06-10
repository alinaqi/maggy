"""Tests for Telos data models — IntentNode, IFSScore, TelosResult."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MODELS_PATH = (
    Path(__file__).resolve().parent.parent
    / "plugins" / "telos" / "models.py"
)


def _load_models():
    import sys
    spec = importlib.util.spec_from_file_location(
        "telos_models", _MODELS_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["telos_models"] = mod
    spec.loader.exec_module(mod)
    return mod


_m = _load_models()
IntentNode = _m.IntentNode
IFSScore = _m.IFSScore
TelosResult = _m.TelosResult


class TestIntentNode:
    """IntentNode maps to a Cortex reasons row."""

    def test_from_dict_minimal(self):
        row = {
            "id": "R-001",
            "goal": "Add JWT auth",
            "owner": "alice",
            "status": "proposed",
            "created_at": "2026-05-20T10:00:00",
        }
        node = IntentNode.from_dict(row)
        assert node.id == "R-001"
        assert node.goal == "Add JWT auth"
        assert node.owner == "alice"
        assert node.scope == []
        assert node.preconditions == []
        assert node.anti_criteria == []

    def test_from_dict_full(self):
        row = {
            "id": "R-002",
            "goal": "OAuth2 migration",
            "decision_type": "architecture",
            "scope": '["auth/", "middleware/"]',
            "owner": "bob",
            "status": "fulfilled",
            "preconditions": '["JWT must work"]',
            "postconditions": '["OAuth2 tokens valid"]',
            "invariants": '["session not broken"]',
            "anti_criteria": '["no plaintext tokens"]',
            "parent_id": "R-001",
            "created_at": "2026-05-20T10:00:00",
            "fulfilled_at": "2026-05-22T14:00:00",
        }
        node = IntentNode.from_dict(row)
        assert node.decision_type == "architecture"
        assert node.scope == ["auth/", "middleware/"]
        assert node.anti_criteria == ["no plaintext tokens"]
        assert node.parent_id == "R-001"
        assert node.fulfilled_at == "2026-05-22T14:00:00"

    def test_from_dict_json_parse_fallback(self):
        row = {
            "id": "R-003",
            "goal": "test",
            "owner": "x",
            "status": "proposed",
            "created_at": "2026-01-01",
            "scope": "not-json",
            "anti_criteria": None,
        }
        node = IntentNode.from_dict(row)
        assert node.scope == []
        assert node.anti_criteria == []

    def test_has_contracts(self):
        empty = IntentNode.from_dict({
            "id": "R-004", "goal": "g", "owner": "o",
            "status": "proposed", "created_at": "2026-01-01",
        })
        assert not empty.has_contracts

        with_pre = IntentNode.from_dict({
            "id": "R-005", "goal": "g", "owner": "o",
            "status": "proposed", "created_at": "2026-01-01",
            "preconditions": '["x"]',
        })
        assert with_pre.has_contracts


class TestIFSScore:
    """IFS = F1 * F2 * F3, multiplicative."""

    def test_composite_all_perfect(self):
        score = IFSScore(f1=1.0, f2=1.0, f3=1.0)
        assert score.composite == pytest.approx(1.0)

    def test_composite_zero_plane_collapses(self):
        score = IFSScore(f1=0.0, f2=1.0, f3=1.0)
        assert score.composite == pytest.approx(0.0)

    def test_composite_partial(self):
        score = IFSScore(f1=0.8, f2=0.9, f3=0.7)
        assert score.composite == pytest.approx(0.504)

    def test_details_stored(self):
        score = IFSScore(
            f1=1.0, f2=0.5, f3=1.0,
            details={"drift_count": 3},
        )
        assert score.details["drift_count"] == 3

    def test_computed_at_auto(self):
        score = IFSScore(f1=1.0, f2=1.0, f3=1.0)
        assert score.computed_at is not None


class TestTelosResult:
    """TelosResult bundles IFS + supporting data."""

    def test_construction(self):
        ifs = IFSScore(f1=0.9, f2=0.8, f3=0.7)
        result = TelosResult(
            project="myapp",
            ifs=ifs,
            test_results={"passed": 9, "failed": 1},
            drift_signals=[{"id": "D-1", "severity": 0.5}],
            intent_bugs=["orphan: fn_x"],
            anti_criteria_violations=[],
        )
        assert result.project == "myapp"
        assert result.ifs.composite == pytest.approx(0.504)
        assert len(result.drift_signals) == 1
        assert result.anti_criteria_violations == []

    def test_to_dict(self):
        ifs = IFSScore(f1=1.0, f2=1.0, f3=1.0)
        result = TelosResult(
            project="p",
            ifs=ifs,
            test_results={},
            drift_signals=[],
            intent_bugs=[],
            anti_criteria_violations=[],
        )
        d = result.to_dict()
        assert d["project"] == "p"
        assert d["ifs"]["composite"] == pytest.approx(1.0)
        assert "f1" in d["ifs"]
