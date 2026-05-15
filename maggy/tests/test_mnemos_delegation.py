"""Tests for sub-agent delegation protocol."""

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.delegation import (
    build_delegation_context,
    classify_inheritance,
    filter_nodes_for_delegation,
    merge_delegation_results,
)
from maggy.mnemos.models import MnemoNode


def _node(
    ntype: str = "GoalNode",
    scope: list[str] | None = None,
) -> MnemoNode:
    return MnemoNode(
        type=ntype,
        task_id="t1",
        content="test content",
        scope_tags=scope or [],
    )


class TestClassifyInheritance:
    def test_goal_is_full(self):
        assert classify_inheritance(_node("GoalNode")) == "FULL"

    def test_constraint_is_full(self):
        assert classify_inheritance(_node("ConstraintNode")) == "FULL"

    def test_decision_is_reference(self):
        assert classify_inheritance(_node("DecisionNode")) == "REFERENCE"

    def test_context_is_scope(self):
        assert classify_inheritance(_node("ContextNode")) == "SCOPE"

    def test_error_is_none(self):
        assert classify_inheritance(_node("ErrorNode")) == "NONE"

    def test_skill_is_full(self):
        assert classify_inheritance(_node("SkillNode")) == "FULL"


class TestFilterNodes:
    def test_includes_full(self):
        nodes = [_node("GoalNode")]
        result = filter_nodes_for_delegation(nodes, ["any"])
        assert len(result) == 1

    def test_excludes_none(self):
        nodes = [_node("ErrorNode")]
        result = filter_nodes_for_delegation(nodes, ["any"])
        assert result == []

    def test_scope_filter(self):
        n = _node("ContextNode", scope=["auth"])
        result = filter_nodes_for_delegation([n], ["auth"])
        assert len(result) == 1

    def test_scope_filter_no_overlap(self):
        n = _node("ContextNode", scope=["auth"])
        result = filter_nodes_for_delegation([n], ["billing"])
        assert result == []

    def test_reference_strips_content(self):
        n = _node("DecisionNode")
        result = filter_nodes_for_delegation([n], [])
        assert result[0].content.startswith("[ref:")


class TestBuildDelegationContext:
    def test_filters_active(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        db.insert_node(_node("GoalNode"))
        db.insert_node(MnemoNode(
            type="ErrorNode", task_id="t1",
            content="e", status="ACTIVE",
        ))
        ctx = build_delegation_context(db, [], "t1")
        types = [n.type for n in ctx]
        assert "GoalNode" in types
        assert "ErrorNode" not in types


class TestMergeDelegationResults:
    def test_merges_result_nodes(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        nodes = [
            _node("ResultNode"),
            _node("SkillNode"),
            _node("GoalNode"),
        ]
        count = merge_delegation_results(db, nodes)
        assert count == 2  # ResultNode + SkillNode
