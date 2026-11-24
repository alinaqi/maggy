"""scripts/mnemos store, consolidation and checkpoint behaviour.

Ported from the deleted maggy.mnemos db/consolidation/checkpoint tests onto
the kept implementation (scripts/mnemos, importable as `mnemos`).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from mnemos.checkpoint import load_checkpoint, write_checkpoint
from mnemos.consolidation import micro_consolidate
from mnemos.models import MnemoNode
from mnemos.store import MnemosStore


@pytest.fixture()
def store(tmp_path: Path) -> MnemosStore:
    created = MnemosStore(str(tmp_path))
    created.init_db()
    return created


def test_init_creates_gitignored_dir(store: MnemosStore) -> None:
    assert store.exists()
    assert (store.mnemos_dir / ".gitignore").read_text() == "*\n"


def test_create_and_get_node_roundtrip(store: MnemosStore) -> None:
    node = MnemoNode(type="goal", task_id="t1", content="Ship it",
                     scope_tags=["api"])
    store.create_node(node)
    loaded = store.get_node(node.id)
    assert loaded is not None
    assert (loaded.content, loaded.scope_tags) == ("Ship it", ["api"])


def test_get_by_type_filters(store: MnemosStore) -> None:
    store.create_node(MnemoNode(type="goal", task_id="t", content="g"))
    store.create_node(MnemoNode(type="result", task_id="t", content="r"))
    assert [n.content for n in store.get_by_type("result")] == ["r"]


def test_goal_nodes_are_never_evictable() -> None:
    goal = MnemoNode(type="goal", task_id="t", content="g")
    context = MnemoNode(type="context", task_id="t", content="c")
    assert not goal.is_evictable and context.is_evictable


def test_micro_consolidate_compresses_results(store: MnemosStore) -> None:
    for i in range(4):
        store.create_node(MnemoNode(type="result", task_id="t",
                                    content=f"result {i}"))
    stats = micro_consolidate(store, max_compress=3)
    assert stats["compressed"] == 3
    assert len(store.get_by_type("result", status="active")) == 1


def test_checkpoint_captures_goal_and_constraints(store: MnemosStore) -> None:
    store.create_node(MnemoNode(type="goal", task_id="t9", content="Fix bug"))
    store.create_node(MnemoNode(type="constraint", task_id="t9",
                                content="No new deps"))
    cp = write_checkpoint(store, fatigue_score=0.5)
    assert (cp.task_id, cp.goal) == ("t9", "Fix bug")
    assert cp.active_constraints == ["No new deps"]
    latest = json.loads((store.mnemos_dir / "checkpoint-latest.json")
                        .read_text())
    assert latest["goal"] == "Fix bug"


def test_load_checkpoint_formats_context(store: MnemosStore) -> None:
    store.create_node(MnemoNode(type="goal", task_id="t", content="Do X"))
    write_checkpoint(store)
    text = load_checkpoint(str(store.project_dir))
    assert text is not None and "Do X" in text


def test_load_checkpoint_missing_returns_none(tmp_path: Path) -> None:
    assert load_checkpoint(str(tmp_path)) is None
