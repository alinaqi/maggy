"""Sub-agent inheritance rules and scope filtering."""

from __future__ import annotations

from pathlib import Path

from maggy.mnemos.checkpoint import write_checkpoint
from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import CheckpointData, MnemoNode
from maggy.mnemos.scope import scope_overlap

INHERITANCE_RULES: dict[str, str] = {
    "GoalNode": "FULL",
    "ConstraintNode": "FULL",
    "DecisionNode": "REFERENCE",
    "CodeRefNode": "SCOPE",
    "FactNode": "SCOPE",
    "ErrorNode": "NONE",
    "SkillNode": "FULL",
    "ContextNode": "SCOPE",
    "ResultNode": "NONE",
    "WorkingNode": "NONE",
    "CheckpointNode": "NONE",
    "HandoffNode": "NONE",
}


def classify_inheritance(node: MnemoNode) -> str:
    """Return inheritance rule for a node type."""
    return INHERITANCE_RULES.get(node.type, "NONE")


def filter_nodes_for_delegation(
    nodes: list[MnemoNode], scope_tags: list[str],
) -> list[MnemoNode]:
    """Apply inheritance rules + scope filtering."""
    result: list[MnemoNode] = []
    for node in nodes:
        rule = classify_inheritance(node)
        if rule == "NONE":
            continue
        if rule == "SCOPE":
            if scope_overlap(node.scope_tags, scope_tags) < 0.1:
                continue
        if rule == "REFERENCE":
            node = _strip_to_reference(node)
        result.append(node)
    return result


def build_delegation_context(
    db: MnemosDB, scope_tags: list[str], task_id: str,
) -> list[MnemoNode]:
    """Build the node set to hand to a sub-agent."""
    all_nodes = db.list_nodes()
    active = [n for n in all_nodes if n.status == "ACTIVE"]
    return filter_nodes_for_delegation(active, scope_tags)


def create_delegation_checkpoint(
    db: MnemosDB, mnemos_dir: Path,
    scope_tags: list[str], task_id: str,
) -> CheckpointData:
    """Create a checkpoint with only delegated nodes."""
    return write_checkpoint(
        mnemos_dir, db, task_id=task_id, fatigue=0.0, force=True,
    )


def merge_delegation_results(
    parent_db: MnemosDB, child_nodes: list[MnemoNode],
) -> int:
    """Merge sub-agent results back into parent."""
    count = 0
    for node in child_nodes:
        if node.type in ("ResultNode", "SkillNode", "FactNode"):
            parent_db.insert_node(node)
            count += 1
    return count


def _strip_to_reference(node: MnemoNode) -> MnemoNode:
    """Strip content for REFERENCE inheritance."""
    return MnemoNode(
        id=node.id,
        type=node.type,
        task_id=node.task_id,
        content=f"[ref:{node.id}] {node.type}",
        summary=node.summary,
        scope_tags=node.scope_tags,
    )
