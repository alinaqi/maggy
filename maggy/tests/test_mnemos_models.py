"""Tests for mnemos Pydantic models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from maggy.mnemos.models import (
    CheckpointData,
    FatigueState,
    MnemoNode,
    NodeLink,
)


class TestMnemoNode:
    def test_create_goal_node(self):
        node = MnemoNode(
            type="GoalNode",
            task_id="task-1",
            content="Implement auth",
        )
        assert node.type == "GoalNode"
        assert node.status == "ACTIVE"
        assert node.activation_weight == 1.0
        assert node.id  # auto-generated

    def test_rejects_invalid_type(self):
        with pytest.raises(ValidationError):
            MnemoNode(
                type="BogusNode",
                task_id="t",
                content="x",
            )

    def test_auto_generates_id(self):
        a = MnemoNode(type="FactNode", task_id="t", content="x")
        b = MnemoNode(type="FactNode", task_id="t", content="x")
        assert a.id != b.id

    def test_timestamps_auto_set(self):
        node = MnemoNode(
            type="DecisionNode",
            task_id="t",
            content="chose X",
        )
        assert isinstance(node.created_at, datetime)
        assert isinstance(node.last_accessed, datetime)

    def test_scope_tags_default_empty(self):
        node = MnemoNode(
            type="FactNode", task_id="t", content="x",
        )
        assert node.scope_tags == []


class TestFatigueState:
    def test_flow_state(self):
        fs = FatigueState(score=0.2, token_util=0.5)
        assert fs.state == "FLOW"

    def test_compress_state(self):
        fs = FatigueState(score=0.5, token_util=1.0)
        assert fs.state == "COMPRESS"

    def test_pre_sleep_state(self):
        fs = FatigueState(score=0.7, token_util=1.0)
        assert fs.state == "PRE_SLEEP"

    def test_emergency_state(self):
        fs = FatigueState(score=0.95, token_util=1.0)
        assert fs.state == "EMERGENCY"

    def test_needs_checkpoint(self):
        fs = FatigueState(score=0.65, token_util=1.0)
        assert fs.needs_checkpoint is True

    def test_no_checkpoint_in_flow(self):
        fs = FatigueState(score=0.3, token_util=0.5)
        assert fs.needs_checkpoint is False


class TestCheckpointData:
    def test_create_checkpoint(self):
        cp = CheckpointData(
            task_id="task-1",
            fatigue=0.65,
            summary="Mid-session checkpoint",
            graph_json={"nodes": [], "links": []},
        )
        assert cp.id
        assert cp.is_emergency is False

    def test_emergency_checkpoint(self):
        cp = CheckpointData(
            task_id="task-1",
            fatigue=0.92,
            summary="Emergency",
            graph_json={"nodes": []},
            is_emergency=True,
        )
        assert cp.is_emergency is True


class TestNodeLink:
    def test_create_link(self):
        link = NodeLink(
            source_id="a",
            target_id="b",
        )
        assert link.link_type == "RELATED"

    def test_custom_link_type(self):
        link = NodeLink(
            source_id="a",
            target_id="b",
            link_type="DEPENDS_ON",
        )
        assert link.link_type == "DEPENDS_ON"
