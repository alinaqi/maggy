"""Tests for mnemos checkpoint logic."""

import json
import time
from pathlib import Path

import pytest

from maggy.mnemos.checkpoint import (
    format_for_context,
    is_cooldown_active,
    write_checkpoint,
)
from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import MnemoNode


@pytest.fixture()
def db(tmp_mnemos_dir: Path) -> MnemosDB:
    return MnemosDB(tmp_mnemos_dir)


class TestWriteCheckpoint:
    def test_creates_checkpoint_file(
        self, tmp_mnemos_dir: Path, db: MnemosDB,
    ):
        db.insert_node(MnemoNode(
            type="GoalNode", task_id="t1", content="ship",
        ))
        cp = write_checkpoint(
            tmp_mnemos_dir, db, task_id="t1", fatigue=0.65,
        )
        assert cp is not None
        assert cp.fatigue == 0.65
        latest = tmp_mnemos_dir / "checkpoint-latest.json"
        assert latest.exists()

    def test_checkpoint_contains_nodes(
        self, tmp_mnemos_dir: Path, db: MnemosDB,
    ):
        db.insert_node(MnemoNode(
            type="GoalNode", task_id="t1", content="goal1",
        ))
        db.insert_node(MnemoNode(
            type="FactNode", task_id="t1", content="fact1",
        ))
        cp = write_checkpoint(
            tmp_mnemos_dir, db, task_id="t1", fatigue=0.5,
        )
        assert len(cp.graph_json["nodes"]) == 2

    def test_emergency_flag(
        self, tmp_mnemos_dir: Path, db: MnemosDB,
    ):
        cp = write_checkpoint(
            tmp_mnemos_dir, db,
            task_id="t1", fatigue=0.92, emergency=True,
        )
        assert cp.is_emergency is True

    def test_force_skips_cooldown(
        self, tmp_mnemos_dir: Path, db: MnemosDB,
    ):
        write_checkpoint(
            tmp_mnemos_dir, db, task_id="t1", fatigue=0.6,
        )
        cp2 = write_checkpoint(
            tmp_mnemos_dir, db,
            task_id="t1", fatigue=0.7, force=True,
        )
        assert cp2 is not None


class TestCooldown:
    def test_no_cooldown_initially(self, tmp_mnemos_dir: Path):
        assert is_cooldown_active(tmp_mnemos_dir) is False

    def test_cooldown_after_checkpoint(
        self, tmp_mnemos_dir: Path, db: MnemosDB,
    ):
        write_checkpoint(
            tmp_mnemos_dir, db, task_id="t1", fatigue=0.6,
        )
        assert is_cooldown_active(tmp_mnemos_dir) is True


class TestFormatForContext:
    def test_format_includes_summary(
        self, tmp_mnemos_dir: Path, db: MnemosDB,
    ):
        db.insert_node(MnemoNode(
            type="GoalNode", task_id="t1", content="build X",
        ))
        cp = write_checkpoint(
            tmp_mnemos_dir, db, task_id="t1", fatigue=0.6,
        )
        text = format_for_context(cp)
        assert "MNEMOS CHECKPOINT" in text
        assert "GoalNode" in text

    def test_format_empty_graph(
        self, tmp_mnemos_dir: Path, db: MnemosDB,
    ):
        cp = write_checkpoint(
            tmp_mnemos_dir, db, task_id="t1", fatigue=0.3,
        )
        text = format_for_context(cp)
        assert "MNEMOS CHECKPOINT" in text
