"""HandoffNode generation with fleet diagnostics."""

from __future__ import annotations

from pathlib import Path

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import MnemoNode
from maggy.mnemos.signals import read_signals


def build_handoff_node(
    db: MnemosDB, mnemos_dir: Path, task_id: str,
) -> MnemoNode:
    """Create a HandoffNode with full context."""
    content = _build_content(db, mnemos_dir)
    return MnemoNode(
        type="HandoffNode",
        task_id=task_id,
        content=content,
    )


def _build_content(db: MnemosDB, mnemos_dir: Path) -> str:
    parts: list[str] = []
    parts.append(_section_goals(db))
    parts.append(_section_decisions(db))
    parts.append(_section_skills(db))
    parts.append(_section_diagnostics(db, mnemos_dir))
    return "\n".join(parts)


def _section_goals(db: MnemosDB) -> str:
    goals = db.list_nodes(node_type="GoalNode")
    active = [g for g in goals if g.status == "ACTIVE"]
    lines = ["## Active Goals"]
    for g in active:
        lines.append(f"- {g.content[:80]}")
    if not active:
        lines.append("- (none)")
    return "\n".join(lines)


def _section_decisions(db: MnemosDB) -> str:
    decisions = db.list_nodes(node_type="DecisionNode")
    lines = ["## Key Decisions"]
    for d in decisions[:10]:
        lines.append(f"- {d.content[:80]}")
    if not decisions:
        lines.append("- (none)")
    return "\n".join(lines)


def _section_skills(db: MnemosDB) -> str:
    skills = db.list_nodes(node_type="SkillNode")
    lines = ["## Promoted Skills"]
    for s in skills[:10]:
        lines.append(f"- {s.content[:80]}")
    if not skills:
        lines.append("- (none)")
    return "\n".join(lines)


def _section_diagnostics(
    db: MnemosDB, mnemos_dir: Path,
) -> str:
    signals = read_signals(mnemos_dir)
    nodes = db.list_nodes()
    active = sum(1 for n in nodes if n.status == "ACTIVE")
    compressed = sum(
        1 for n in nodes if n.status == "COMPRESSED"
    )
    evicted = sum(
        1 for n in nodes if n.status == "EVICTED"
    )
    return (
        "## Fleet Diagnostics\n"
        f"- Total nodes: {len(nodes)}\n"
        f"- Active: {active}\n"
        f"- Compressed: {compressed}\n"
        f"- Evicted: {evicted}\n"
        f"- Total signals: {len(signals)}"
    )


def format_handoff(node: MnemoNode) -> str:
    """Format a HandoffNode for display."""
    return f"--- HANDOFF ---\n{node.content}\n--- END ---"
