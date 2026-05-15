"""SkillNode fingerprinting, equivalence, and promotion."""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from maggy.mnemos.constants import (
    FP_STANDARD_THRESHOLD,
    FP_STRONG_THRESHOLD,
    FP_WEAK_THRESHOLD,
    SKILL_CONFIDENCE_CAP,
    SKILL_PROMOTION_COUNT,
    SKILL_REINFORCE_BOOST,
)
from maggy.mnemos.db import MnemosDB
from maggy.mnemos.db_queries import update_node_fingerprint, update_node_weight
from maggy.mnemos.models import MnemoNode

EmbeddingFn = Callable[[str], str]


def structural_hash(content: str) -> str:
    """SHA256 of normalized content."""
    normalized = content.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def outcome_signature(node: MnemoNode) -> str:
    """Hash of type + status + scope_tags."""
    raw = f"{node.type}:{node.status}:{sorted(node.scope_tags)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def compute_fingerprint(
    node: MnemoNode,
    embed_fn: EmbeddingFn = structural_hash,
) -> str:
    """3-signal fingerprint: struct|embed|outcome."""
    s1 = structural_hash(node.content)
    s2 = embed_fn(node.content)
    s3 = outcome_signature(node)
    return f"{s1}|{s2}|{s3}"


def fingerprint_similarity(fp_a: str, fp_b: str) -> float:
    """Compare fingerprints. Returns 0.0-1.0."""
    parts_a = fp_a.split("|")
    parts_b = fp_b.split("|")
    if len(parts_a) != 3 or len(parts_b) != 3:
        return 0.0
    matches = sum(
        1 for a, b in zip(parts_a, parts_b) if a == b
    )
    return matches / 3.0


def classify_equivalence(similarity: float) -> str:
    """Classify: strong/standard/weak/none."""
    if similarity >= FP_STRONG_THRESHOLD:
        return "strong"
    if similarity >= FP_STANDARD_THRESHOLD:
        return "standard"
    if similarity >= FP_WEAK_THRESHOLD:
        return "weak"
    return "none"


def should_promote(
    node: MnemoNode, occurrence_count: int,
) -> bool:
    """Promote if count >= threshold and not already a Skill."""
    return (
        occurrence_count >= SKILL_PROMOTION_COUNT
        and node.type != "SkillNode"
    )


def promote_to_skill(
    node: MnemoNode, db: MnemosDB,
) -> MnemoNode:
    """Create a SkillNode from a pattern node."""
    fp = compute_fingerprint(node)
    skill = MnemoNode(
        type="SkillNode",
        task_id=node.task_id,
        content=node.content,
        confidence=0.6,
        fingerprint=fp,
        scope_tags=node.scope_tags,
    )
    db.insert_node(skill)
    return skill


def reinforce_skill(
    skill: MnemoNode, db: MnemosDB,
) -> None:
    """Boost activation_weight by REINFORCE_BOOST."""
    new_weight = min(
        skill.activation_weight + SKILL_REINFORCE_BOOST,
        SKILL_CONFIDENCE_CAP,
    )
    update_node_weight(db.conn, skill.id, new_weight)
