"""Guard: Mnemos is consolidated onto scripts/mnemos.

maggy/maggy/mnemos keeps only the v0 compat API (FatigueTracker, SignalLog)
and the fatigue routing thresholds, which the executor and model router still
import. The duplicate memory graph (db, cli, rem, checkpoint, ...) is gone;
scripts/mnemos (`python3 -m mnemos`, used by hooks and commands) is the kept
implementation.
"""

from __future__ import annotations

import importlib
import importlib.util

import pytest

DEAD_MODULES = [
    "__main__", "activation", "checkpoint", "cli", "cli_hooks", "cli_nodes",
    "consolidation", "db", "db_queries", "delegation", "extraction",
    "fatigue", "fatigue_dimensions", "handoff", "merge", "models",
    "orchestrator", "rem", "rem_pruning", "rem_skills", "rem_slow_wave",
    "rem_wake", "scope", "signals", "skills", "status",
]
LIVE_CONSTANTS = {
    "FATIGUE_PARALLEL_BLOCK", "FATIGUE_ROUTING_ESCALATE",
    "FATIGUE_ROUTING_PREMIUM",
}


@pytest.mark.parametrize("name", DEAD_MODULES)
def test_duplicate_mnemos_module_is_gone(name: str) -> None:
    assert importlib.util.find_spec(f"maggy.mnemos.{name}") is None


def test_compat_api_is_kept() -> None:
    package = importlib.import_module("maggy.mnemos")
    assert package.FatigueTracker and package.SignalLog


def test_constants_keep_only_live_thresholds() -> None:
    constants = importlib.import_module("maggy.mnemos.constants")
    public = {n for n in vars(constants) if n.isupper()}
    assert public == LIVE_CONSTANTS


def test_scripts_mnemos_is_the_kept_implementation() -> None:
    assert importlib.util.find_spec("mnemos.store") is not None
    assert importlib.util.find_spec("mnemos.__main__") is not None
