"""Tests for mnemos database layer."""

from pathlib import Path

import pytest

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import CheckpointData, MnemoNode, NodeLink


@pytest.fixture()
def db(tmp_mnemos_dir: Path) -> MnemosDB:
    return MnemosDB(tmp_mnemos_dir)


class TestSchema:
    def test_creates_tables(self, db: MnemosDB):
        tables = db.list_tables()
        assert "mnemo_nodes" in tables
        assert "node_links" in tables
        assert "checkpoints" in tables

    def test_wal_mode_enabled(self, db: MnemosDB):
        row = db.conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"


class TestContextManager:
    def test_closes_on_exit(self, tmp_mnemos_dir: Path):
        with MnemosDB(tmp_mnemos_dir) as db:
            db.insert_node(MnemoNode(
                type="FactNode", task_id="t1", content="f",
            ))
        # After exit, connection should be closed
        with pytest.raises(Exception):
            db.conn.execute("SELECT 1")

    def test_usable_inside_with(self, tmp_mnemos_dir: Path):
        with MnemosDB(tmp_mnemos_dir) as db:
            db.insert_node(MnemoNode(
                type="GoalNode", task_id="t1", content="g",
            ))
            assert db.count_nodes() == 1


class TestNodeCRUD:
    def test_insert_and_get(self, db: MnemosDB):
        node = MnemoNode(
            type="GoalNode", task_id="t1", content="ship it",
        )
        db.insert_node(node)
        got = db.get_node(node.id)
        assert got is not None
        assert got.content == "ship it"

    def test_get_missing_returns_none(self, db: MnemosDB):
        assert db.get_node("nonexistent") is None

    def test_list_by_task(self, db: MnemosDB):
        for i in range(3):
            db.insert_node(MnemoNode(
                type="FactNode", task_id="t1", content=f"f{i}",
            ))
        db.insert_node(MnemoNode(
            type="FactNode", task_id="t2", content="other",
        ))
        nodes = db.list_nodes(task_id="t1")
        assert len(nodes) == 3

    def test_list_by_type(self, db: MnemosDB):
        db.insert_node(MnemoNode(
            type="GoalNode", task_id="t1", content="g",
        ))
        db.insert_node(MnemoNode(
            type="FactNode", task_id="t1", content="f",
        ))
        goals = db.list_nodes(node_type="GoalNode")
        assert len(goals) == 1

    def test_count_nodes(self, db: MnemosDB):
        db.insert_node(MnemoNode(
            type="GoalNode", task_id="t1", content="g",
        ))
        db.insert_node(MnemoNode(
            type="FactNode", task_id="t1", content="f",
        ))
        assert db.count_nodes() == 2

    def test_touch_updates_access(self, db: MnemosDB):
        node = MnemoNode(
            type="FactNode", task_id="t1", content="f",
        )
        db.insert_node(node)
        db.touch_node(node.id)
        got = db.get_node(node.id)
        assert got is not None
        assert got.access_count == 1


class TestLinkCRUD:
    def test_insert_link(self, db: MnemosDB):
        a = MnemoNode(type="GoalNode", task_id="t", content="a")
        b = MnemoNode(type="FactNode", task_id="t", content="b")
        db.insert_node(a)
        db.insert_node(b)
        db.insert_link(NodeLink(source_id=a.id, target_id=b.id))
        links = db.get_links(a.id)
        assert len(links) == 1
        assert links[0].target_id == b.id


class TestCheckpointCRUD:
    def test_insert_and_get_latest(self, db: MnemosDB):
        cp = CheckpointData(
            task_id="t1",
            fatigue=0.65,
            summary="mid session",
            graph_json={"nodes": []},
        )
        db.insert_checkpoint(cp)
        latest = db.get_latest_checkpoint()
        assert latest is not None
        assert latest.summary == "mid session"

    def test_latest_is_most_recent(self, db: MnemosDB):
        for i in range(3):
            db.insert_checkpoint(CheckpointData(
                task_id="t1",
                fatigue=0.5 + i * 0.1,
                summary=f"cp{i}",
                graph_json={},
            ))
        latest = db.get_latest_checkpoint()
        assert latest is not None
        assert latest.summary == "cp2"
