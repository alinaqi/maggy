"""Tests for self-improvement signals and analysis."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from maggy.improve.models import (
    ImprovementReport,
    Recommendation,
    SignalBundle,
)


# ── Models ───────────────────────────────────────────────────────────────


class TestModels:
    def test_recommendation_defaults(self):
        rec = Recommendation(
            category="routing",
            severity="info",
            message="test",
            suggestion="do something",
        )
        assert rec.data == {}

    def test_signal_bundle_defaults(self):
        bundle = SignalBundle()
        assert bundle.routing == {}
        assert bundle.collected_at == ""

    def test_improvement_report(self):
        report = ImprovementReport(
            generated_at="2025-01-01",
            total_signals=3,
            recommendations=[],
            health_summary={"routing": 0.8},
            top_actions=["fix routing"],
        )
        assert report.total_signals == 3


# ── Signal Collectors ────────────────────────────────────────────────────


class TestCollectRouting:
    def test_collects_heatmap(self):
        from maggy.improve.signals import collect_routing
        routing = MagicMock()
        routing.get_heatmap.return_value = [
            {"model": "a", "task_type": "bug", "avg_reward": 0.8, "count": 10},
        ]
        result = collect_routing(routing)
        assert len(result["heatmap"]) == 1
        assert result["underperformers"] == []

    def test_flags_underperformers(self):
        from maggy.improve.signals import collect_routing
        routing = MagicMock()
        routing.get_heatmap.return_value = [
            {"model": "bad", "task_type": "bug", "avg_reward": 0.2, "count": 10},
        ]
        result = collect_routing(routing)
        assert len(result["underperformers"]) == 1


class TestCollectEvents:
    def test_calculates_failure_rate(self):
        from maggy.improve.signals import collect_events
        events = MagicMock()
        events.query.return_value = [
            {"success": True}, {"success": False},
            {"success": True}, {"success": True},
        ]
        result = collect_events(events)
        assert result["total"] == 4
        assert result["failures"] == 1
        assert result["failure_rate"] == 0.25

    def test_empty_events(self):
        from maggy.improve.signals import collect_events
        events = MagicMock()
        events.query.return_value = []
        result = collect_events(events)
        assert result["failure_rate"] == 0.0


class TestCollectHistory:
    def test_returns_patterns(self):
        from maggy.improve.signals import collect_history
        history = MagicMock()
        history.get_report.return_value = {
            "total_sessions": 50,
            "patterns": ["dominance"],
            "by_provider": {"claude": 40, "codex": 10},
        }
        result = collect_history(history)
        assert result["sessions"] == 50

    def test_no_report(self):
        from maggy.improve.signals import collect_history
        history = MagicMock()
        history.get_report.return_value = None
        result = collect_history(history)
        assert result["sessions"] == 0


class TestCollectForge:
    def test_returns_gaps(self):
        from maggy.improve.signals import collect_forge
        forge = MagicMock()
        forge.get_gaps.return_value = [
            {"name": "slack", "count": 5},
        ]
        result = collect_forge(forge)
        assert result["count"] == 1


class TestCollectEngram:
    def test_returns_health(self):
        from maggy.improve.signals import collect_engram
        engram = MagicMock()
        with patch("maggy.engram.diagnostics.diagnose") as mock_diag:
            profile = SimpleNamespace(
                health_score=0.7, total_memories=100,
                active_count=70, superseded_count=30,
            )
            mock_diag.return_value = profile
            result = collect_engram(engram)
        assert result["health_score"] == 0.7


class TestCollectBudget:
    def test_returns_status(self):
        from maggy.improve.signals import collect_budget
        budget = MagicMock()
        budget.budget_status.return_value = {
            "utilization": 0.5, "status": "ok",
        }
        result = collect_budget(budget)
        assert result["utilization"] == 0.5


class TestCollectAll:
    def test_skips_none_services(self):
        from maggy.improve.signals import collect_all
        state = SimpleNamespace(
            routing=None, events=None, history=None,
            forge=None, engram=None, budget=None,
        )
        bundle = collect_all(state)
        assert bundle.routing == {}
        assert bundle.events == {}


# ── Analyzer ─────────────────────────────────────────────────────────────


class TestAnalyzeRouting:
    def test_flags_underperformers(self):
        from maggy.improve.analyzer import analyze_routing
        signals = SignalBundle(
            routing={"underperformers": [
                {"model": "bad", "task_type": "bug", "avg_reward": 0.2},
            ]},
        )
        recs = analyze_routing(signals)
        assert len(recs) == 1
        assert recs[0].category == "routing"

    def test_no_issues(self):
        from maggy.improve.analyzer import analyze_routing
        signals = SignalBundle(routing={"underperformers": []})
        assert analyze_routing(signals) == []


class TestAnalyzeFailures:
    def test_flags_high_failure(self):
        from maggy.improve.analyzer import analyze_failures
        signals = SignalBundle(events={"failure_rate": 0.25})
        recs = analyze_failures(signals)
        assert len(recs) == 1
        assert recs[0].severity == "action"

    def test_ok_rate(self):
        from maggy.improve.analyzer import analyze_failures
        signals = SignalBundle(events={"failure_rate": 0.1})
        assert analyze_failures(signals) == []


class TestAnalyzeUsage:
    def test_flags_low_usage(self):
        from maggy.improve.analyzer import analyze_usage
        signals = SignalBundle(history={
            "sessions": 100,
            "by_provider": {"codex": 3},
        })
        recs = analyze_usage(signals)
        assert len(recs) == 1
        assert recs[0].category == "usage"

    def test_no_sessions(self):
        from maggy.improve.analyzer import analyze_usage
        signals = SignalBundle(history={"sessions": 0})
        assert analyze_usage(signals) == []


class TestAnalyzeGaps:
    def test_surfaces_gaps(self):
        from maggy.improve.analyzer import analyze_gaps
        signals = SignalBundle(forge={
            "gaps": [{"name": "slack", "count": 5}],
        })
        recs = analyze_gaps(signals)
        assert len(recs) == 1
        assert recs[0].category == "capability"


class TestAnalyzeMemory:
    def test_flags_low_health(self):
        from maggy.improve.analyzer import analyze_memory
        signals = SignalBundle(engram={"health_score": 0.3})
        recs = analyze_memory(signals)
        assert len(recs) == 1
        assert recs[0].category == "memory"

    def test_healthy(self):
        from maggy.improve.analyzer import analyze_memory
        signals = SignalBundle(engram={"health_score": 0.8})
        assert analyze_memory(signals) == []


class TestAnalyzeCost:
    def test_flags_high_util(self):
        from maggy.improve.analyzer import analyze_cost
        signals = SignalBundle(budget={"utilization": 0.95})
        recs = analyze_cost(signals)
        assert len(recs) == 1
        assert recs[0].category == "cost"

    def test_ok_util(self):
        from maggy.improve.analyzer import analyze_cost
        signals = SignalBundle(budget={"utilization": 0.5})
        assert analyze_cost(signals) == []


class TestAnalyzeAll:
    def test_merges_all(self):
        from maggy.improve.analyzer import analyze_all
        signals = SignalBundle(
            routing={"underperformers": [
                {"model": "x", "task_type": "bug", "avg_reward": 0.1},
            ]},
            events={"failure_rate": 0.3},
            budget={"utilization": 0.95},
            engram={"health_score": 0.2},
            forge={"gaps": [{"name": "y", "count": 3}]},
            history={"sessions": 0},
        )
        recs = analyze_all(signals)
        categories = {r.category for r in recs}
        assert "routing" in categories
        assert "reliability" in categories
        assert "cost" in categories


# ── Introspector Service ─────────────────────────────────────────────────


class TestIntrospector:
    def test_analyze_empty_state(self):
        from maggy.improve.service import Introspector
        state = SimpleNamespace(
            routing=None, events=None, history=None,
            forge=None, engram=None, budget=None,
        )
        intro = Introspector(state)
        report = intro.analyze()
        assert report.total_signals == 0
        assert report.recommendations == []

    def test_get_report_none_initially(self):
        from maggy.improve.service import Introspector
        state = SimpleNamespace(
            routing=None, events=None, history=None,
            forge=None, engram=None, budget=None,
        )
        intro = Introspector(state)
        assert intro.get_report() is None

    def test_get_report_after_analyze(self):
        from maggy.improve.service import Introspector
        state = SimpleNamespace(
            routing=None, events=None, history=None,
            forge=None, engram=None, budget=None,
        )
        intro = Introspector(state)
        intro.analyze()
        report = intro.get_report()
        assert report is not None
        assert report.generated_at != ""

    def test_health_summary_populated(self):
        from maggy.improve.service import Introspector
        routing = MagicMock()
        routing.get_heatmap.return_value = []
        events = MagicMock()
        events.query.return_value = [
            {"success": True}, {"success": True},
        ]
        budget = MagicMock()
        budget.budget_status.return_value = {
            "utilization": 0.5, "status": "ok",
        }
        state = SimpleNamespace(
            routing=routing, events=events, history=None,
            forge=None, engram=None, budget=budget,
        )
        intro = Introspector(state)
        report = intro.analyze()
        assert "routing" in report.health_summary
        assert "reliability" in report.health_summary
        assert "cost" in report.health_summary
