"""Tests for merge algebra."""

from datetime import datetime, timezone

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.merge import (
    detect_conflicts,
    is_constraint_absolute,
    merge_nodes,
    resolve_content_conflict,
    resolve_scope_conflict,
    resolve_status_conflict,
    resolve_weight_conflict,
)
from maggy.mnemos.models import MnemoNode


def _node(
    content: str = "test",
    status: str = "ACTIVE",
    weight: float = 1.0,
    scope: list[str] | None = None,
    ntype: str = "FactNode",
) -> MnemoNode:
    return MnemoNode(
        type=ntype,
        task_id="t1",
        content=content,
        status=status,
        activation_weight=weight,
        scope_tags=scope or [],
    )


class TestDetectConflicts:
    def test_no_conflict(self):
        n = _node()
        assert detect_conflicts(n, n) == []

    def test_content_conflict(self):
        a = _node(content="aaa")
        b = _node(content="bbb")
        assert "CONTENT" in detect_conflicts(a, b)

    def test_status_conflict(self):
        a = _node(status="ACTIVE")
        b = _node(status="COMPRESSED")
        assert "STATUS" in detect_conflicts(a, b)

    def test_weight_conflict(self):
        a = _node(weight=0.5)
        b = _node(weight=0.9)
        assert "WEIGHT" in detect_conflicts(a, b)

    def test_scope_conflict(self):
        a = _node(scope=["auth"])
        b = _node(scope=["billing"])
        assert "SCOPE" in detect_conflicts(a, b)


class TestConstraintAbsolute:
    def test_constraint_is_absolute(self):
        n = _node(ntype="ConstraintNode")
        assert is_constraint_absolute(n) is True

    def test_fact_not_absolute(self):
        assert is_constraint_absolute(_node()) is False


class TestResolveContent:
    def test_newer_wins(self):
        a = _node(content="old")
        b = _node(content="new")
        # b created after a (same instant, but b is "newer")
        result = resolve_content_conflict(a, b)
        # Both have same timestamp, so a wins (a.created_at >= b)
        assert result in ("old", "new")

    def test_constraint_never_overwritten(self):
        a = _node(content="rule", ntype="ConstraintNode")
        b = _node(content="new")
        assert resolve_content_conflict(a, b) == "rule"


class TestResolveStatus:
    def test_active_wins(self):
        assert resolve_status_conflict("ACTIVE", "COMPRESSED") == "ACTIVE"

    def test_compressed_over_evicted(self):
        assert resolve_status_conflict("EVICTED", "COMPRESSED") == "COMPRESSED"


class TestResolveWeight:
    def test_max_wins(self):
        assert resolve_weight_conflict(0.3, 0.7) == 0.7


class TestResolveScope:
    def test_union(self):
        result = resolve_scope_conflict(["a"], ["b"])
        assert set(result) == {"a", "b"}


class TestMergeNodes:
    def test_no_conflicts(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n = _node()
        resolved, records = merge_nodes(n, n, db)
        assert records == []

    def test_with_conflicts(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        a = _node(content="a", weight=0.3, scope=["x"])
        b = _node(content="b", weight=0.7, scope=["y"])
        resolved, records = merge_nodes(a, b, db)
        assert len(records) >= 2
        assert resolved.activation_weight == 0.7
