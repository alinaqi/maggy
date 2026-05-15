"""Tests for HandoffNode generation."""

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.handoff import (
    build_handoff_node,
    format_handoff,
)
from maggy.mnemos.models import MnemoNode


class TestBuildHandoffNode:
    def test_creates_handoff(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        node = build_handoff_node(db, tmp_mnemos_dir, "t1")
        assert node.type == "HandoffNode"
        assert "Active Goals" in node.content

    def test_includes_goals(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        g = MnemoNode(
            type="GoalNode", task_id="t1",
            content="Build feature X",
        )
        db.insert_node(g)
        node = build_handoff_node(db, tmp_mnemos_dir, "t1")
        assert "Build feature X" in node.content

    def test_includes_decisions(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        d = MnemoNode(
            type="DecisionNode", task_id="t1",
            content="Use SQLite",
        )
        db.insert_node(d)
        node = build_handoff_node(db, tmp_mnemos_dir, "t1")
        assert "Use SQLite" in node.content

    def test_includes_diagnostics(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        node = build_handoff_node(db, tmp_mnemos_dir, "t1")
        assert "Fleet Diagnostics" in node.content
        assert "Total nodes:" in node.content

    def test_includes_skills(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        s = MnemoNode(
            type="SkillNode", task_id="t1",
            content="Pattern: Read -> Edit -> Write",
        )
        db.insert_node(s)
        node = build_handoff_node(db, tmp_mnemos_dir, "t1")
        assert "Pattern:" in node.content


class TestFormatHandoff:
    def test_wraps_content(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        node = build_handoff_node(db, tmp_mnemos_dir, "t1")
        output = format_handoff(node)
        assert output.startswith("--- HANDOFF ---")
        assert output.endswith("--- END ---")
