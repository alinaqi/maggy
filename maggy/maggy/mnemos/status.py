"""Status display for mnemos CLI."""

from __future__ import annotations

from pathlib import Path

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.fatigue import load_fatigue
from maggy.mnemos.models import FatigueState


def render_status(mnemos_dir: Path, db: MnemosDB) -> str:
    """Render status summary for CLI output."""
    lines: list[str] = ["mnemos status", ""]
    _add_node_counts(lines, db)
    _add_fatigue(lines, mnemos_dir)
    _add_checkpoint(lines, db)
    return "\n".join(lines)


def _add_node_counts(lines: list[str], db: MnemosDB) -> None:
    total = db.count_nodes()
    lines.append(f"Nodes: {total}")
    if total > 0:
        nodes = db.list_nodes()
        by_type: dict[str, int] = {}
        for n in nodes:
            by_type[n.type] = by_type.get(n.type, 0) + 1
        for t, c in sorted(by_type.items()):
            lines.append(f"  {t}: {c}")


def _add_fatigue(lines: list[str], mnemos_dir: Path) -> None:
    fs = load_fatigue(mnemos_dir)
    if fs is None:
        lines.append("Fatigue: not measured yet")
        return
    lines.append(
        f"Fatigue: {fs.score:.2f} ({fs.state})"
    )


def _add_checkpoint(lines: list[str], db: MnemosDB) -> None:
    cp = db.get_latest_checkpoint()
    if cp is None:
        lines.append("Last checkpoint: none")
        return
    lines.append(
        f"Last checkpoint: {cp.created_at:%H:%M:%S} "
        f"(fatigue={cp.fatigue:.2f})"
    )
