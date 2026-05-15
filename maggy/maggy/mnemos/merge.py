"""Merge algebra — 5 conflict types with absolute rules."""

from __future__ import annotations

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import ConflictRecord, MnemoNode, NodeLink
from maggy.mnemos.scope import merge_scope_tags

CONFLICT_CONTENT = "CONTENT"
CONFLICT_STATUS = "STATUS"
CONFLICT_WEIGHT = "WEIGHT"
CONFLICT_LINK = "LINK"
CONFLICT_SCOPE = "SCOPE"

STATUS_PRECEDENCE = ["ACTIVE", "COMPRESSED", "EVICTED", "CRYSTALLIZED"]


def detect_conflicts(
    node_a: MnemoNode, node_b: MnemoNode,
) -> list[str]:
    """Compare two nodes and return conflict types."""
    conflicts: list[str] = []
    if node_a.content != node_b.content:
        conflicts.append(CONFLICT_CONTENT)
    if node_a.status != node_b.status:
        conflicts.append(CONFLICT_STATUS)
    if abs(node_a.activation_weight - node_b.activation_weight) > 0.01:
        conflicts.append(CONFLICT_WEIGHT)
    if set(node_a.scope_tags) != set(node_b.scope_tags):
        conflicts.append(CONFLICT_SCOPE)
    return conflicts


def is_constraint_absolute(node: MnemoNode) -> bool:
    """ConstraintNodes have absolute merge protection."""
    return node.type == "ConstraintNode"


def resolve_content_conflict(
    node_a: MnemoNode, node_b: MnemoNode,
) -> str:
    """Newer content wins. Constraints never overwritten."""
    if is_constraint_absolute(node_a):
        return node_a.content
    if node_b.created_at > node_a.created_at:
        return node_b.content
    return node_a.content


def resolve_status_conflict(
    status_a: str, status_b: str,
) -> str:
    """Status with higher precedence wins."""
    idx_a = _status_index(status_a)
    idx_b = _status_index(status_b)
    return status_a if idx_a <= idx_b else status_b


def resolve_weight_conflict(
    weight_a: float, weight_b: float,
) -> float:
    """Take the maximum weight (optimistic merge)."""
    return max(weight_a, weight_b)


def resolve_scope_conflict(
    tags_a: list[str], tags_b: list[str],
) -> list[str]:
    """Union of scope tags."""
    return merge_scope_tags(tags_a, tags_b)


def merge_nodes(
    node_a: MnemoNode, node_b: MnemoNode, db: MnemosDB,
) -> tuple[MnemoNode, list[ConflictRecord]]:
    """Full merge. Returns resolved node + conflict records."""
    conflicts = detect_conflicts(node_a, node_b)
    records: list[ConflictRecord] = []
    content = node_a.content
    status = node_a.status
    weight = node_a.activation_weight
    tags = node_a.scope_tags
    for ct in conflicts:
        resolution = _resolve(ct, node_a, node_b)
        records.append(ConflictRecord(
            node_a_id=node_a.id,
            node_b_id=node_b.id,
            conflict_type=ct,
            resolution=resolution,
        ))
        if ct == CONFLICT_CONTENT:
            content = resolve_content_conflict(node_a, node_b)
        elif ct == CONFLICT_STATUS:
            status = resolve_status_conflict(node_a.status, node_b.status)
        elif ct == CONFLICT_WEIGHT:
            weight = resolve_weight_conflict(
                node_a.activation_weight, node_b.activation_weight,
            )
        elif ct == CONFLICT_SCOPE:
            tags = resolve_scope_conflict(node_a.scope_tags, node_b.scope_tags)
    resolved = MnemoNode(
        id=node_a.id,
        type=node_a.type,
        task_id=node_a.task_id,
        content=content,
        status=status,
        activation_weight=weight,
        scope_tags=tags,
        confidence=max(node_a.confidence, node_b.confidence),
    )
    return resolved, records


def _resolve(ct: str, a: MnemoNode, b: MnemoNode) -> str:
    if ct == CONFLICT_CONTENT and is_constraint_absolute(a):
        return "CONSTRAINT_ABSOLUTE: kept original"
    return f"Resolved {ct}: preferred {'a' if a.created_at >= b.created_at else 'b'}"


def _status_index(status: str) -> int:
    try:
        return STATUS_PRECEDENCE.index(status)
    except ValueError:
        return len(STATUS_PRECEDENCE)
