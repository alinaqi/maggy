"""REM Process — orchestrates all 4 phases."""

from __future__ import annotations

from pathlib import Path

from maggy.mnemos.constants import REM_TRIGGER_THRESHOLD
from maggy.mnemos.db import MnemosDB
from maggy.mnemos.rem_pruning import run_task_pruning
from maggy.mnemos.rem_skills import run_skill_consolidation
from maggy.mnemos.rem_slow_wave import run_slow_wave
from maggy.mnemos.rem_wake import count_active_nodes, run_wake_reconstruction


def should_trigger_rem(fatigue_score: float) -> bool:
    """True if fatigue >= 0.75 (PRE_SLEEP or higher)."""
    return fatigue_score >= REM_TRIGGER_THRESHOLD


def run_rem_cycle(db: MnemosDB, mnemos_dir: Path) -> dict:
    """Execute all 4 REM phases in sequence."""
    pre_count = count_active_nodes(db)
    p1 = run_slow_wave(db)
    p2 = run_skill_consolidation(db)
    p3 = run_task_pruning(db)
    p4 = run_wake_reconstruction(db, pre_count)
    return {
        "slow_wave": p1,
        "skills": p2,
        "pruning": p3,
        "wake": p4,
        "pre_rem_count": pre_count,
    }


def format_rem_report(stats: dict) -> str:
    """Human-readable REM summary."""
    sw = stats.get("slow_wave", {})
    sk = stats.get("skills", {})
    pr = stats.get("pruning", {})
    wk = stats.get("wake", {})
    lines = [
        "--- MNEMOS REM CYCLE ---",
        f"Phase 1 (Slow-Wave): {sw.get('compressed', 0)} compressed, "
        f"{sw.get('evicted', 0)} evicted",
        f"Phase 2 (Skills): {sk.get('promoted', 0)} promoted",
        f"Phase 3 (Pruning): {pr.get('crystallized_tasks', 0)} tasks crystallized",
        f"Phase 4 (Wake): {wk.get('wake_nodes', 0)} nodes in wake context "
        f"({wk.get('ratio', 0):.0%} of pre-REM)",
        "--- END REM ---",
    ]
    return "\n".join(lines)
