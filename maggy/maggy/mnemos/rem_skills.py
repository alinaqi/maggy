"""REM Phase 2: Skill Consolidation — fingerprint and promote."""

from __future__ import annotations

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import MnemoNode
from maggy.mnemos.skills import (
    compute_fingerprint,
    promote_to_skill,
    reinforce_skill,
    should_promote,
)


def find_skill_candidates(db: MnemosDB) -> list[MnemoNode]:
    """WorkingNodes and ResultNodes for skill detection."""
    working = db.list_nodes(node_type="WorkingNode")
    results = db.list_nodes(node_type="ResultNode")
    active = [
        n for n in [*working, *results]
        if n.status == "ACTIVE"
    ]
    return active


def group_by_fingerprint(
    nodes: list[MnemoNode],
) -> dict[str, list[MnemoNode]]:
    """Group nodes by their computed fingerprint."""
    groups: dict[str, list[MnemoNode]] = {}
    for node in nodes:
        fp = compute_fingerprint(node)
        groups.setdefault(fp, []).append(node)
    return groups


def promote_recurring_patterns(
    db: MnemosDB,
    groups: dict[str, list[MnemoNode]],
) -> list[MnemoNode]:
    """Promote groups with count >= 3 to SkillNodes."""
    promoted: list[MnemoNode] = []
    existing_skills = db.list_nodes(node_type="SkillNode")
    existing_fps = {s.fingerprint for s in existing_skills}
    for fp, nodes in groups.items():
        if not should_promote(nodes[0], len(nodes)):
            continue
        if fp in existing_fps:
            _reinforce_matching(db, existing_skills, fp)
            continue
        skill = promote_to_skill(nodes[0], db)
        promoted.append(skill)
    return promoted


def _reinforce_matching(
    db: MnemosDB,
    skills: list[MnemoNode],
    fp: str,
) -> None:
    for s in skills:
        if s.fingerprint == fp:
            reinforce_skill(s, db)
            break


def run_skill_consolidation(db: MnemosDB) -> dict:
    """Execute Phase 2."""
    candidates = find_skill_candidates(db)
    groups = group_by_fingerprint(candidates)
    promoted = promote_recurring_patterns(db, groups)
    return {"promoted": len(promoted), "candidates": len(candidates)}
