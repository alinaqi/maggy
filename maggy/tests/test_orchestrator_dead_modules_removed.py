"""Guard: dead orchestrator submodules stay deleted; kept ones still import."""

from __future__ import annotations

import importlib
import importlib.util

import pytest

DEAD = (
    "adapters", "sources", "router",
    "scoring", "identity", "events",
    "store", "state_machine", "orchestrator",
    "workspace", "__main__", "config",
)
KEPT = (
    "worktree", "merge", "merge_rollback",
    "models", "isolation",
)


@pytest.mark.parametrize("name", DEAD)
def test_dead_orchestrator_module_is_gone(name: str) -> None:
    spec = importlib.util.find_spec(f"maggy.orchestrator.{name}")
    assert spec is None, f"maggy.orchestrator.{name} should be deleted"


@pytest.mark.parametrize("name", KEPT)
def test_kept_orchestrator_module_imports(name: str) -> None:
    assert importlib.import_module(f"maggy.orchestrator.{name}")
