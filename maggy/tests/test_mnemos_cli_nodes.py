"""Tests for CLI node management commands."""

import subprocess
import sys
from pathlib import Path

from maggy.mnemos.db import MnemosDB


class TestCmdAdd:
    def test_add_goal(self, mock_cwd):
        d = mock_cwd / ".mnemos"
        d.mkdir()
        MnemosDB(d)
        result = subprocess.run(
            [sys.executable, "-m", "mnemos", "add", "goal", "Test goal"],
            cwd=str(mock_cwd),
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "GoalNode" in result.stdout

    def test_add_constraint(self, mock_cwd):
        d = mock_cwd / ".mnemos"
        d.mkdir()
        MnemosDB(d)
        result = subprocess.run(
            [sys.executable, "-m", "mnemos", "add", "constraint", "No deps"],
            cwd=str(mock_cwd),
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "ConstraintNode" in result.stdout


class TestCmdListNodes:
    def test_list_empty(self, mock_cwd):
        d = mock_cwd / ".mnemos"
        d.mkdir()
        MnemosDB(d)
        result = subprocess.run(
            [sys.executable, "-m", "mnemos", "nodes"],
            cwd=str(mock_cwd),
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "No nodes" in result.stdout

    def test_list_with_type_filter(self, mock_cwd):
        d = mock_cwd / ".mnemos"
        d.mkdir()
        db = MnemosDB(d)
        from maggy.mnemos.models import MnemoNode
        db.insert_node(MnemoNode(
            type="GoalNode", task_id="t1", content="g",
        ))
        db.insert_node(MnemoNode(
            type="FactNode", task_id="t1", content="f",
        ))
        result = subprocess.run(
            [sys.executable, "-m", "mnemos", "nodes", "--type", "GoalNode"],
            cwd=str(mock_cwd),
            capture_output=True, text=True,
        )
        assert "GoalNode" in result.stdout
        assert "FactNode" not in result.stdout
