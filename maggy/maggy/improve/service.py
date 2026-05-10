"""Introspector — orchestrates signal collection and analysis."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .analyzer import analyze_all
from .models import ImprovementReport, SignalBundle
from .signals import collect_all

logger = logging.getLogger(__name__)


class Introspector:
    """Collect signals, analyze, persist recommendations."""

    def __init__(self, app_state) -> None:
        self._state = app_state
        self._last_report: ImprovementReport | None = None

    def analyze(self) -> ImprovementReport:
        """Run full analysis cycle."""
        signals = collect_all(self._state)
        recs = analyze_all(signals)
        report = self._build_report(signals, recs)
        self._persist(report)
        self._last_report = report
        return report

    def get_report(self) -> ImprovementReport | None:
        """Return the most recent report."""
        return self._last_report

    def _build_report(self, signals, recs) -> ImprovementReport:
        total = sum(
            1 for v in (
                signals.routing, signals.events,
                signals.history, signals.forge,
                signals.engram, signals.budget,
            )
            if v
        )
        actions = [
            r.message for r in recs if r.severity == "action"
        ][:3]
        health = self._health_summary(signals)
        return ImprovementReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_signals=total,
            recommendations=recs,
            health_summary=health,
            top_actions=actions,
        )

    def _health_summary(self, s: SignalBundle) -> dict:
        summary: dict = {}
        if s.routing:
            bad = len(s.routing.get("underperformers", []))
            summary["routing"] = 0.5 if bad else 1.0
        if s.engram:
            summary["memory"] = s.engram.get("health_score", 1.0)
        if s.events:
            rate = s.events.get("failure_rate", 0)
            summary["reliability"] = round(1.0 - rate, 2)
        if s.budget:
            util = s.budget.get("utilization", 0)
            summary["cost"] = round(1.0 - util, 2)
        return summary

    def _persist(self, report: ImprovementReport) -> None:
        """Write report as engram + emit mutation events."""
        engram = getattr(self._state, "engram", None)
        if engram:
            self._write_engram(engram, report)
        events = getattr(self._state, "events", None)
        if events:
            self._emit_mutations(events, report)

    def _write_engram(self, engram, report) -> None:
        from maggy.engram.record import EngramRecord
        import uuid
        try:
            record = EngramRecord(
                engram_id=uuid.uuid4().hex[:12],
                namespace="self-improvement",
                memory_type="fact",
                content=f"Report: {len(report.recommendations)} recs",
                tags=["auto-improve"],
            )
            engram.write(record)
        except Exception as exc:
            logger.warning("Failed to write engram: %s", exc)

    def _emit_mutations(self, events, report) -> None:
        from maggy.event_spine.events import MutationEvent
        from maggy.event_spine.header import EventHeader
        for rec in report.recommendations:
            if rec.severity != "action":
                continue
            try:
                evt = MutationEvent(
                    header=EventHeader(event_type="mutation"),
                    control_level="advisory",
                    target=rec.category,
                    old_value="",
                    new_value=rec.suggestion,
                    reason=rec.message,
                )
                events.emit(evt)
            except Exception as exc:
                logger.warning("Failed to emit: %s", exc)
