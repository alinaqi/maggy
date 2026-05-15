"""Tests for checkpoint format compatibility.

Verifies load_latest() and format_for_context() handle both:
- Standard CheckpointData format (written by Python module)
- Rich template format (written by bash hook scripts)
"""

import json
from pathlib import Path

import pytest

from maggy.mnemos.checkpoint import (
    format_for_context,
    load_latest,
    write_checkpoint,
)
from maggy.mnemos.constants import CHECKPOINT_LATEST
from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import MnemoNode


RICH_CHECKPOINT = {
    "id": "abc-123",
    "task_id": "live-test",
    "goal": "Implement cross-agent intelligence",
    "active_constraints": [
        "All agents must share iCPG state",
        "No secrets in hooks",
    ],
    "active_results": [
        "Fixed hook scripts with defensive pattern",
        "Added 2>/dev/null guards",
    ],
    "current_subgoal": "Wire fatigue routing",
    "working_memory": "Checking model routing",
    "task_narrative": "Fixed hooks, now wiring routing",
    "recent_files": [
        {"path": "src/routing.py", "edits": 3, "reads": 5},
    ],
    "fatigue_at_checkpoint": 0.47,
    "git_state": {
        "branch": "feature/mnemos",
        "uncommitted": ["src/routing.py", "src/hooks.py"],
    },
    "icpg_state": None,
    "node_summary": {
        "total": 6,
        "active": 6,
        "compressed": 0,
        "by_type": {"goal": 2, "constraint": 2, "result": 2},
    },
    "created_at": "2026-05-15T22:06:29.302671+00:00",
}


@pytest.fixture()
def db(tmp_mnemos_dir: Path) -> MnemosDB:
    return MnemosDB(tmp_mnemos_dir)


def _write_rich(mnemos_dir: Path, data: dict) -> None:
    path = mnemos_dir / CHECKPOINT_LATEST
    path.write_text(json.dumps(data, indent=2))


class TestLoadLatestRichFormat:
    """load_latest() must handle rich template checkpoints."""

    def test_loads_without_crash(self, tmp_mnemos_dir: Path):
        _write_rich(tmp_mnemos_dir, RICH_CHECKPOINT)
        cp = load_latest(tmp_mnemos_dir)
        assert cp is not None

    def test_preserves_goal(self, tmp_mnemos_dir: Path):
        _write_rich(tmp_mnemos_dir, RICH_CHECKPOINT)
        cp = load_latest(tmp_mnemos_dir)
        assert cp is not None
        assert cp.goal == "Implement cross-agent intelligence"

    def test_preserves_constraints(self, tmp_mnemos_dir: Path):
        _write_rich(tmp_mnemos_dir, RICH_CHECKPOINT)
        cp = load_latest(tmp_mnemos_dir)
        assert cp is not None
        assert len(cp.active_constraints) == 2

    def test_preserves_results(self, tmp_mnemos_dir: Path):
        _write_rich(tmp_mnemos_dir, RICH_CHECKPOINT)
        cp = load_latest(tmp_mnemos_dir)
        assert cp is not None
        assert len(cp.active_results) == 2

    def test_maps_fatigue(self, tmp_mnemos_dir: Path):
        _write_rich(tmp_mnemos_dir, RICH_CHECKPOINT)
        cp = load_latest(tmp_mnemos_dir)
        assert cp is not None
        assert cp.fatigue == pytest.approx(0.47)

    def test_preserves_git_state(self, tmp_mnemos_dir: Path):
        _write_rich(tmp_mnemos_dir, RICH_CHECKPOINT)
        cp = load_latest(tmp_mnemos_dir)
        assert cp is not None
        assert cp.git_state["branch"] == "feature/mnemos"


class TestLoadLatestStandardFormat:
    """load_latest() must still work with standard format."""

    def test_roundtrips_standard(
        self, tmp_mnemos_dir: Path, db: MnemosDB,
    ):
        db.insert_node(MnemoNode(
            type="GoalNode", task_id="t1", content="ship",
        ))
        original = write_checkpoint(
            tmp_mnemos_dir, db, task_id="t1", fatigue=0.65,
        )
        loaded = load_latest(tmp_mnemos_dir)
        assert loaded is not None
        assert loaded.id == original.id
        assert loaded.fatigue == 0.65

    def test_standard_has_graph_json(
        self, tmp_mnemos_dir: Path, db: MnemosDB,
    ):
        db.insert_node(MnemoNode(
            type="GoalNode", task_id="t1", content="goal",
        ))
        write_checkpoint(
            tmp_mnemos_dir, db, task_id="t1", fatigue=0.5,
        )
        loaded = load_latest(tmp_mnemos_dir)
        assert loaded is not None
        assert "nodes" in loaded.graph_json


class TestFormatRichCheckpoint:
    """format_for_context() outputs rich info from template checkpoints."""

    def test_includes_goal(self, tmp_mnemos_dir: Path):
        _write_rich(tmp_mnemos_dir, RICH_CHECKPOINT)
        cp = load_latest(tmp_mnemos_dir)
        text = format_for_context(cp)
        assert "cross-agent intelligence" in text

    def test_includes_constraints(self, tmp_mnemos_dir: Path):
        _write_rich(tmp_mnemos_dir, RICH_CHECKPOINT)
        cp = load_latest(tmp_mnemos_dir)
        text = format_for_context(cp)
        assert "iCPG state" in text

    def test_includes_results(self, tmp_mnemos_dir: Path):
        _write_rich(tmp_mnemos_dir, RICH_CHECKPOINT)
        cp = load_latest(tmp_mnemos_dir)
        text = format_for_context(cp)
        assert "defensive pattern" in text

    def test_includes_git_branch(self, tmp_mnemos_dir: Path):
        _write_rich(tmp_mnemos_dir, RICH_CHECKPOINT)
        cp = load_latest(tmp_mnemos_dir)
        text = format_for_context(cp)
        assert "feature/mnemos" in text
