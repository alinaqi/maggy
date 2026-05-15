"""Checkpoint write/read/format logic."""

from __future__ import annotations

import json
import time
from pathlib import Path

from maggy.mnemos.constants import (
    CHECKPOINT_COOLDOWN_S,
    CHECKPOINT_LATEST,
)
from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import CheckpointData


def is_cooldown_active(mnemos_dir: Path) -> bool:
    """Check if checkpoint cooldown is still active."""
    latest = mnemos_dir / CHECKPOINT_LATEST
    if not latest.exists():
        return False
    age = time.time() - latest.stat().st_mtime
    return age < CHECKPOINT_COOLDOWN_S


def write_checkpoint(
    mnemos_dir: Path,
    db: MnemosDB,
    *,
    task_id: str,
    fatigue: float,
    emergency: bool = False,
    force: bool = False,
) -> CheckpointData:
    """Write a checkpoint to DB and latest file."""
    if not force and is_cooldown_active(mnemos_dir):
        latest = db.get_latest_checkpoint()
        if latest:
            return latest
    nodes = db.list_nodes()
    graph = _build_graph_json(nodes)
    summary = _build_summary(nodes, fatigue)
    cp = CheckpointData(
        task_id=task_id,
        fatigue=fatigue,
        summary=summary,
        graph_json=graph,
        is_emergency=emergency,
    )
    db.insert_checkpoint(cp)
    _write_latest(mnemos_dir, cp)
    return cp


def _build_graph_json(nodes: list) -> dict:
    return {
        "nodes": [
            {
                "id": n.id,
                "type": n.type,
                "content": n.content,
                "status": n.status,
            }
            for n in nodes
        ],
    }


def _build_summary(nodes: list, fatigue: float) -> str:
    by_type: dict[str, int] = {}
    for n in nodes:
        by_type[n.type] = by_type.get(n.type, 0) + 1
    parts = [f"{t}:{c}" for t, c in sorted(by_type.items())]
    type_str = ", ".join(parts) if parts else "empty"
    return f"fatigue={fatigue:.2f} nodes={type_str}"


def _write_latest(mnemos_dir: Path, cp: CheckpointData) -> None:
    path = mnemos_dir / CHECKPOINT_LATEST
    data = cp.model_dump(mode="json")
    path.write_text(json.dumps(data, indent=2))


def load_latest(mnemos_dir: Path) -> CheckpointData | None:
    """Load checkpoint-latest.json (standard or rich format)."""
    path = mnemos_dir / CHECKPOINT_LATEST
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    # Rich format uses fatigue_at_checkpoint instead of fatigue
    if "fatigue_at_checkpoint" in data and "fatigue" not in data:
        data["fatigue"] = data.pop("fatigue_at_checkpoint")
    return CheckpointData(**data)


def format_for_context(cp: CheckpointData) -> str:
    """Format checkpoint for injection into Claude context."""
    lines = ["--- MNEMOS CHECKPOINT ---"]
    if cp.goal:
        return _format_rich(cp, lines)
    return _format_standard(cp, lines)


def _format_rich(cp: CheckpointData, lines: list[str]) -> str:
    """Format a rich (template-written) checkpoint."""
    lines.append(f"Goal: {cp.goal}")
    lines.append(f"Task: {cp.task_id} | Fatigue: {cp.fatigue:.2f}")
    lines.append("")
    if cp.active_constraints:
        lines.append("Constraints (DO NOT VIOLATE):")
        for c in cp.active_constraints:
            lines.append(f"  - {c}")
        lines.append("")
    if cp.active_results:
        lines.append("Completed Results:")
        for r in cp.active_results:
            lines.append(f"  - {r}")
        lines.append("")
    if cp.current_subgoal:
        lines.append(f"Current Sub-Goal: {cp.current_subgoal}")
    if cp.task_narrative:
        lines.append(f"Activity: {cp.task_narrative}")
    git = cp.git_state
    if git.get("branch"):
        lines.append(f"Branch: {git['branch']}")
        uncommitted = git.get("uncommitted", [])
        if uncommitted:
            lines.append(
                "Uncommitted: " + ", ".join(uncommitted[:5])
            )
    lines.append("--- END CHECKPOINT ---")
    return "\n".join(lines)


def _format_standard(
    cp: CheckpointData, lines: list[str],
) -> str:
    """Format a standard (Python-written) checkpoint."""
    lines.append(
        f"Task: {cp.task_id} | Fatigue: {cp.fatigue:.2f}"
    )
    lines.append(f"Emergency: {cp.is_emergency}")
    if cp.summary:
        lines.append(f"Summary: {cp.summary}")
    lines.append("")
    nodes = cp.graph_json.get("nodes", [])
    if nodes:
        lines.append("Active nodes:")
        for n in nodes:
            lines.append(
                f"  [{n['type']}] {n['content'][:80]}"
            )
    else:
        lines.append("No active nodes.")
    lines.append("--- END CHECKPOINT ---")
    return "\n".join(lines)
