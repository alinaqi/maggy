"""Tests for REM Phase 3: Task Graph Pruning."""

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.db_queries import update_node_status
from maggy.mnemos.models import MnemoNode
from maggy.mnemos.rem_pruning import (
    crystallize_task,
    find_completed_tasks,
    run_task_pruning,
)


class TestFindCompletedTasks:
    def test_finds_completed(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        g = MnemoNode(
            type="GoalNode", task_id="done",
            content="goal", status="ACTIVE",
        )
        db.insert_node(g)
        update_node_status(db.conn, g.id, "COMPRESSED")
        completed = find_completed_tasks(db)
        assert "done" in completed

    def test_excludes_active_goals(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        g = MnemoNode(
            type="GoalNode", task_id="ongoing",
            content="goal",
        )
        db.insert_node(g)
        completed = find_completed_tasks(db)
        assert "ongoing" not in completed

    def test_no_goals(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        assert find_completed_tasks(db) == []


class TestCrystallizeTask:
    def test_marks_crystallized(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        nodes = [
            MnemoNode(type="FactNode", task_id="t1", content="f"),
            MnemoNode(type="ContextNode", task_id="t1", content="c"),
        ]
        for n in nodes:
            db.insert_node(n)
        count = crystallize_task(db, "t1")
        assert count == 2
        for n in nodes:
            refreshed = db.get_node(n.id)
            assert refreshed.status == "CRYSTALLIZED"


class TestRunTaskPruning:
    def test_full_phase(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        g = MnemoNode(
            type="GoalNode", task_id="done",
            content="g", status="COMPRESSED",
        )
        f = MnemoNode(
            type="FactNode", task_id="done", content="f",
        )
        db.insert_node(g)
        db.insert_node(f)
        stats = run_task_pruning(db)
        assert stats["crystallized_tasks"] == 1
