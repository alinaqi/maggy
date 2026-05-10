"""Tests for Lexon — routing, terminology, disambiguation."""

from __future__ import annotations

from maggy.lexon.disambiguate import disambiguate
from maggy.lexon.personalization import PersonalizationEngine
from maggy.lexon.record import LexonRecord
from maggy.lexon.router import LexonRouter
from maggy.lexon.terminology import TermEntry, TerminologyMap


class TestTerminology:
    def test_resolve_canonical(self):
        tm = TerminologyMap()
        assert tm.resolve("deploy") == "deploy"

    def test_resolve_synonym(self):
        tm = TerminologyMap()
        assert tm.resolve("ship") == "deploy"

    def test_resolve_unknown(self):
        tm = TerminologyMap()
        assert tm.resolve("xyzzy") is None

    def test_add_alias(self):
        tm = TerminologyMap()
        assert tm.add_alias("deploy", "yeet")
        assert tm.resolve("yeet") == "deploy"

    def test_add_alias_unknown_canonical(self):
        tm = TerminologyMap()
        assert not tm.add_alias("nonexistent", "alias")


class TestDisambiguate:
    def test_high_confidence_resolves(self):
        result = disambiguate(0.9, ["grep"])
        assert result.resolved
        assert result.tool == "grep"
        assert result.mode == "none"

    def test_mid_confidence_self_clarify(self):
        result = disambiguate(0.6, ["grep", "glob"])
        assert result.resolved
        assert result.mode == "self_clarify"

    def test_low_confidence_user_clarify(self):
        result = disambiguate(0.4, ["grep", "glob", "find"])
        assert not result.resolved
        assert result.mode == "user_clarify"

    def test_very_low_rejects(self):
        result = disambiguate(0.1, [])
        assert not result.resolved


class TestPersonalization:
    def test_record_and_top(self):
        pe = PersonalizationEngine()
        pe.record_use("grep")
        pe.record_use("grep")
        pe.record_use("glob")
        top = pe.top_tools(2)
        assert top[0] == "grep"

    def test_preferred_alias(self):
        pe = PersonalizationEngine()
        pe.record_alias("find stuff", "grep")
        assert pe.get_preferred("find stuff") == "grep"

    def test_correction(self):
        pe = PersonalizationEngine()
        pe.record_correction("test", "pytest")
        assert len(pe.signals.correction_pairs) == 1


class TestLexonRouter:
    def test_known_intent(self):
        lr = LexonRouter()
        record = lr.route("deploy my app")
        assert record.confidence > 0.5
        assert len(record.candidates) > 0

    def test_unknown_intent(self):
        lr = LexonRouter()
        record = lr.route("xyzzy plugh")
        assert record.confidence < 0.5

    def test_learn_and_recall(self):
        lr = LexonRouter()
        lr.learn("push it live", "vercel_deploy")
        record = lr.route("push it live")
        assert record.resolved_tool == "vercel_deploy"
        assert record.confidence >= 0.9

    def test_multiple_candidates(self):
        lr = LexonRouter()
        record = lr.route("search for files")
        assert len(record.candidates) >= 1


class TestLexonRecord:
    def test_ambiguous(self):
        r = LexonRecord(phrase="test", confidence=0.3)
        assert r.is_ambiguous

    def test_not_ambiguous(self):
        r = LexonRecord(phrase="test", confidence=0.9)
        assert not r.is_ambiguous

    def test_needs_user_input(self):
        r = LexonRecord(
            phrase="x", disambiguation_mode="user_clarify",
        )
        assert r.needs_user_input
