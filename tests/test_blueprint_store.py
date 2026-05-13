"""Tests for blueprint store — SQLite persistence + matching."""
from __future__ import annotations

from pathlib import Path

import pytest

from maggy.blueprint_store import BlueprintStore


@pytest.fixture
def store(tmp_path: Path) -> BlueprintStore:
    return BlueprintStore(tmp_path / "blueprints.db")


def test_record_and_list(store: BlueprintStore):
    store.record(
        "fp1", "docs", ["Read README.md", "$ npm run build"],
        ["report", "generate"], "generate {path} report", "local",
    )
    bps = store.list_all()
    assert len(bps) == 1
    assert bps[0]["fingerprint"] == "fp1"
    assert bps[0]["task_type"] == "docs"


def test_upsert_increments_count(store: BlueprintStore):
    for _ in range(3):
        store.record(
            "fp1", "docs", ["Read x"], ["report"],
            "generate report", "local",
        )
    bps = store.list_all()
    assert len(bps) == 1
    assert bps[0]["success_count"] == 3


def test_match_returns_none_empty(store: BlueprintStore):
    assert store.match("docs", ["report"]) is None


def test_match_needs_min_samples(store: BlueprintStore):
    store.record("fp1", "docs", ["Read x"], ["report"], "t", "local")
    assert store.match("docs", ["report"]) is None


def test_match_by_keywords(store: BlueprintStore):
    for _ in range(4):
        store.record(
            "fp1", "docs",
            ["Read x", "$ npm run build"],
            ["report", "benchmark", "generate"],
            "generate benchmark report", "local",
        )
    result = store.match("docs", ["report", "benchmark"])
    assert result is not None
    assert result["fingerprint"] == "fp1"


def test_match_wrong_type_misses(store: BlueprintStore):
    for _ in range(4):
        store.record(
            "fp1", "docs", ["Read x"],
            ["report"], "t", "local",
        )
    assert store.match("security", ["report"]) is None


def test_record_failure(store: BlueprintStore):
    for _ in range(4):
        store.record("fp1", "docs", ["x"], ["report"], "t", "local")
    store.record_failure("fp1")
    bps = store.list_all()
    assert bps[0]["fail_count"] == 1


def test_low_confidence_not_matched(store: BlueprintStore):
    for _ in range(3):
        store.record("fp1", "docs", ["x"], ["report"], "t", "local")
    for _ in range(10):
        store.record_failure("fp1")
    assert store.match("docs", ["report"]) is None


def test_collective_match_across_blueprints(
    store: BlueprintStore,
):
    """3+ similar blueprints prove a pattern is repeatable."""
    shared = ["benchmark", "generate", "report"]
    for i, company in enumerate(["airbus", "allianz", "continental"]):
        store.record(
            f"fp{i}", "docs", ["Read", "Bash"],
            shared + [company], "t", "claude", "adc",
        )
    result = store.match("docs", shared + ["vaillant"], "adc")
    assert result is not None


def test_project_isolation(store: BlueprintStore):
    """Blueprints from project A don't match in project B."""
    shared = ["benchmark", "generate", "report"]
    for i, c in enumerate(["airbus", "allianz", "continental"]):
        store.record(
            f"fp{i}", "docs", ["Read", "Bash"],
            shared + [c], "t", "claude", "adc",
        )
    assert store.match("docs", shared, "adc") is not None
    assert store.match("docs", shared, "other") is None
