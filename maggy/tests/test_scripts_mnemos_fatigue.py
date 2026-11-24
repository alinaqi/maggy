"""scripts/mnemos signals, fatigue and CLI behaviour.

Ported from the deleted maggy.mnemos signals/fatigue/cli tests onto the kept
implementation (scripts/mnemos, importable as `mnemos`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from mnemos.__main__ import main
from mnemos.fatigue import compute_fatigue
from mnemos.models import FatigueState
from mnemos.signals import (
    append_signal,
    compute_error_density,
    compute_reread_ratio,
    extract_signal_from_post_tool,
    read_recent_signals,
)
from mnemos.store import MnemosStore


@pytest.mark.parametrize("score, state", [
    (0.1, "flow"), (0.5, "compress"), (0.65, "pre_sleep"),
    (0.8, "rem"), (0.95, "emergency"),
])
def test_score_to_state(score: float, state: str) -> None:
    assert FatigueState.score_to_state(score) == state


def test_signals_roundtrip(tmp_path: Path) -> None:
    append_signal(str(tmp_path), {"tool": "Read", "file_path": "a.py"})
    signals = read_recent_signals(str(tmp_path))
    assert signals[0]["tool"] == "Read" and "ts" in signals[0]


def test_reread_and_error_ratios() -> None:
    reads = [{"tool": "Read", "file_path": "a.py"}] * 4
    outcomes = [{"success": True}, {"success": False}]
    assert compute_reread_ratio(reads[:2]) == 0.0  # below 3-read minimum
    assert compute_reread_ratio(reads) == 0.75
    assert compute_error_density(outcomes) == 0.5


def test_post_tool_error_is_a_failure() -> None:
    signal = extract_signal_from_post_tool(
        {"tool_name": "Bash", "tool_response": {"exit_code": 1}})
    assert signal is not None and signal["success"] is False


def test_compute_fatigue_uses_token_utilization(tmp_path: Path) -> None:
    state = compute_fatigue({"used_percentage": 100}, str(tmp_path))
    assert state.token_utilization == 1.0
    assert state.composite_score == pytest.approx(0.40)
    assert state.state == "compress"


def test_cli_add_then_nodes(tmp_path: Path, capsys) -> None:
    project = ["--project", str(tmp_path)]
    assert main([*project, "add", "goal", "Test goal"]) == 0
    assert main([*project, "nodes"]) == 0
    assert "Test goal" in capsys.readouterr().out
    assert len(MnemosStore(str(tmp_path)).get_by_type("goal")) == 1
