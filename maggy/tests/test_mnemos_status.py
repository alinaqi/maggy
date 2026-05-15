"""Tests for status display."""

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.fatigue import save_fatigue
from maggy.mnemos.models import FatigueState, MnemoNode
from maggy.mnemos.status import render_status


class TestRenderStatus:
    def test_empty_db(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        output = render_status(tmp_mnemos_dir, db)
        assert "Nodes: 0" in output
        assert "not measured yet" in output
        assert "none" in output

    def test_with_nodes(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        db.insert_node(MnemoNode(
            type="GoalNode", task_id="t1", content="g",
        ))
        output = render_status(tmp_mnemos_dir, db)
        assert "Nodes: 1" in output
        assert "GoalNode" in output

    def test_with_fatigue(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        fs = FatigueState(score=0.5, token_util=0.5)
        save_fatigue(tmp_mnemos_dir, fs)
        output = render_status(tmp_mnemos_dir, db)
        assert "0.50" in output
        assert "COMPRESS" in output

    def test_with_checkpoint(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        from maggy.mnemos.checkpoint import write_checkpoint
        write_checkpoint(
            tmp_mnemos_dir, db, task_id="t1",
            fatigue=0.6, force=True,
        )
        output = render_status(tmp_mnemos_dir, db)
        assert "fatigue=0.60" in output
