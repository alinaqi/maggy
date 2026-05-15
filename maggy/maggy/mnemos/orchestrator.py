"""Orchestrator signal protocol — 5 signal types."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from maggy.mnemos.constants import ORCHESTRATOR_SIGNALS
from maggy.mnemos.models import CheckpointData, ConflictRecord, FatigueState

SIGNAL_FATIGUE_REPORT = "FATIGUE_REPORT"
SIGNAL_CHECKPOINT_WRITTEN = "CHECKPOINT_WRITTEN"
SIGNAL_REM_COMPLETED = "REM_COMPLETED"
SIGNAL_DELEGATION_REQUEST = "DELEGATION_REQUEST"
SIGNAL_MERGE_CONFLICT = "MERGE_CONFLICT"


@dataclass
class OrchestratorSignal:
    """A signal to/from the orchestrator."""

    signal_type: str
    payload: dict
    timestamp: str = ""
    source_agent: str = "primary"

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


def _append(mnemos_dir: Path, signal: OrchestratorSignal) -> None:
    try:
        path = mnemos_dir / ORCHESTRATOR_SIGNALS
        with path.open("a") as f:
            f.write(json.dumps(asdict(signal)) + "\n")
    except OSError:
        pass


def emit_fatigue_report(
    fatigue: FatigueState, mnemos_dir: Path,
) -> OrchestratorSignal:
    """Create and log a fatigue report signal."""
    sig = OrchestratorSignal(
        signal_type=SIGNAL_FATIGUE_REPORT,
        payload={
            "score": fatigue.score,
            "state": fatigue.state,
            "token_util": fatigue.token_util,
        },
    )
    _append(mnemos_dir, sig)
    return sig


def emit_checkpoint_signal(
    checkpoint: CheckpointData, mnemos_dir: Path,
) -> OrchestratorSignal:
    """Signal that a checkpoint was written."""
    sig = OrchestratorSignal(
        signal_type=SIGNAL_CHECKPOINT_WRITTEN,
        payload={"id": checkpoint.id, "fatigue": checkpoint.fatigue},
    )
    _append(mnemos_dir, sig)
    return sig


def emit_rem_signal(
    rem_stats: dict, mnemos_dir: Path,
) -> OrchestratorSignal:
    """Signal that REM cycle completed."""
    sig = OrchestratorSignal(
        signal_type=SIGNAL_REM_COMPLETED,
        payload=rem_stats,
    )
    _append(mnemos_dir, sig)
    return sig


def emit_delegation_signal(
    task_id: str, scope_tags: list[str], mnemos_dir: Path,
) -> OrchestratorSignal:
    """Signal a delegation request."""
    sig = OrchestratorSignal(
        signal_type=SIGNAL_DELEGATION_REQUEST,
        payload={"task_id": task_id, "scope_tags": scope_tags},
    )
    _append(mnemos_dir, sig)
    return sig


def emit_merge_conflict_signal(
    conflicts: list[ConflictRecord], mnemos_dir: Path,
) -> OrchestratorSignal:
    """Signal merge conflicts."""
    sig = OrchestratorSignal(
        signal_type=SIGNAL_MERGE_CONFLICT,
        payload={"count": len(conflicts)},
    )
    _append(mnemos_dir, sig)
    return sig


def read_orchestrator_signals(
    mnemos_dir: Path,
) -> list[OrchestratorSignal]:
    """Read orchestrator signal log."""
    path = mnemos_dir / ORCHESTRATOR_SIGNALS
    if not path.exists():
        return []
    result: list[OrchestratorSignal] = []
    for line in path.read_text().splitlines():
        try:
            d = json.loads(line)
            result.append(OrchestratorSignal(**d))
        except (json.JSONDecodeError, TypeError):
            continue
    return result
