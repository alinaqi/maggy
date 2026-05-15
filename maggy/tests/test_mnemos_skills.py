"""Tests for SkillNode fingerprinting and promotion."""

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.models import MnemoNode
from maggy.mnemos.skills import (
    classify_equivalence,
    compute_fingerprint,
    fingerprint_similarity,
    outcome_signature,
    promote_to_skill,
    reinforce_skill,
    should_promote,
    structural_hash,
)


def _node(content: str = "test pattern") -> MnemoNode:
    return MnemoNode(
        type="WorkingNode",
        task_id="t1",
        content=content,
    )


class TestStructuralHash:
    def test_deterministic(self):
        h1 = structural_hash("hello")
        h2 = structural_hash("hello")
        assert h1 == h2

    def test_case_insensitive(self):
        h1 = structural_hash("Hello")
        h2 = structural_hash("hello")
        assert h1 == h2

    def test_strips_whitespace(self):
        h1 = structural_hash("  hello  ")
        h2 = structural_hash("hello")
        assert h1 == h2


class TestOutcomeSignature:
    def test_deterministic(self):
        n = _node()
        s1 = outcome_signature(n)
        s2 = outcome_signature(n)
        assert s1 == s2


class TestFingerprint:
    def test_three_parts(self):
        fp = compute_fingerprint(_node())
        parts = fp.split("|")
        assert len(parts) == 3

    def test_identical_nodes_same_fp(self):
        n1 = _node("same content")
        n2 = _node("same content")
        assert compute_fingerprint(n1) == compute_fingerprint(n2)


class TestFingerprintSimilarity:
    def test_identical(self):
        fp = "a|b|c"
        assert fingerprint_similarity(fp, fp) == 1.0

    def test_different(self):
        assert fingerprint_similarity("a|b|c", "x|y|z") == 0.0

    def test_partial(self):
        s = fingerprint_similarity("a|b|c", "a|b|z")
        assert abs(s - 2 / 3) < 0.01

    def test_malformed(self):
        assert fingerprint_similarity("bad", "also_bad") == 0.0


class TestClassifyEquivalence:
    def test_strong(self):
        assert classify_equivalence(0.95) == "strong"

    def test_standard(self):
        assert classify_equivalence(0.85) == "standard"

    def test_weak(self):
        assert classify_equivalence(0.65) == "weak"

    def test_none(self):
        assert classify_equivalence(0.30) == "none"


class TestShouldPromote:
    def test_enough_count(self):
        assert should_promote(_node(), 3) is True

    def test_too_few(self):
        assert should_promote(_node(), 2) is False

    def test_already_skill(self):
        n = MnemoNode(
            type="SkillNode", task_id="t1", content="x",
        )
        assert should_promote(n, 5) is False


class TestPromoteToSkill:
    def test_creates_skill_node(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        n = _node()
        skill = promote_to_skill(n, db)
        assert skill.type == "SkillNode"
        assert skill.fingerprint is not None


class TestReinforceSkill:
    def test_boosts_weight(self, tmp_mnemos_dir):
        db = MnemosDB(tmp_mnemos_dir)
        skill = MnemoNode(
            type="SkillNode", task_id="t1",
            content="pattern", activation_weight=0.5,
        )
        db.insert_node(skill)
        reinforce_skill(skill, db)
        refreshed = db.get_node(skill.id)
        assert refreshed.activation_weight > 0.5
