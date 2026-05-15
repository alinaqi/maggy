"""Tests for REM Phase 2: Skill Consolidation."""

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import MnemoNode
from maggy.mnemos.rem_skills import (
    find_skill_candidates,
    group_by_fingerprint,
    promote_recurring_patterns,
    run_skill_consolidation,
)


def _working(content: str = "pattern") -> MnemoNode:
    return MnemoNode(
        type="WorkingNode", task_id="t1", content=content,
    )


class TestFindSkillCandidates:
    def test_finds_working_nodes(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        db.insert_node(_working())
        cands = find_skill_candidates(db)
        assert len(cands) == 1

    def test_excludes_compressed(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n = MnemoNode(
            type="WorkingNode", task_id="t1",
            content="x", status="COMPRESSED",
        )
        db.insert_node(n)
        assert find_skill_candidates(db) == []


class TestGroupByFingerprint:
    def test_groups_identical(self):
        nodes = [_working("same"), _working("same")]
        groups = group_by_fingerprint(nodes)
        assert any(len(v) == 2 for v in groups.values())

    def test_separates_different(self):
        nodes = [_working("aaa"), _working("bbb")]
        groups = group_by_fingerprint(nodes)
        assert all(len(v) == 1 for v in groups.values())


class TestPromoteRecurring:
    def test_promotes_at_threshold(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        nodes = [_working("same") for _ in range(3)]
        groups = group_by_fingerprint(nodes)
        promoted = promote_recurring_patterns(db, groups)
        assert len(promoted) == 1
        assert promoted[0].type == "SkillNode"

    def test_no_promote_below_threshold(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        nodes = [_working("same") for _ in range(2)]
        groups = group_by_fingerprint(nodes)
        promoted = promote_recurring_patterns(db, groups)
        assert promoted == []


class TestRunSkillConsolidation:
    def test_full_phase(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        for _ in range(3):
            db.insert_node(_working("repeated"))
        stats = run_skill_consolidation(db)
        assert stats["promoted"] >= 1
