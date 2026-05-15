"""Tests for frustration detection service."""
from __future__ import annotations

import time

import pytest

from maggy.services.frustration import (
    FrustrationDetector,
    FrustrationSignal,
    FrustrationTarget,
)


@pytest.fixture()
def detector() -> FrustrationDetector:
    return FrustrationDetector()


# ── Target classification ──────────────────────────────────────────────


class TestTargetClassification:
    def test_app_bug_keywords(self, detector: FrustrationDetector) -> None:
        sig = detector.analyze(
            "i refreshed and no reports are shown",
            history=["show me the reports"],
        )
        assert sig.target == FrustrationTarget.APP_BUG

    def test_output_quality_keywords(
        self, detector: FrustrationDetector,
    ) -> None:
        sig = detector.analyze(
            "no I meant caro kann as BLACK not white",
            history=["show me my caro kann games"],
        )
        assert sig.target == FrustrationTarget.OUTPUT_QUALITY

    def test_task_difficulty_vague(
        self, detector: FrustrationDetector,
    ) -> None:
        sig = detector.analyze(
            "actually nevermind lets do something else",
            history=[
                "help me with the auth flow",
                "hmm what about the tokens",
                "i dont know",
            ],
        )
        assert sig.target == FrustrationTarget.TASK_DIFFICULTY


# ── Score dimensions ───────────────────────────────────────────────────


class TestScoreDimensions:
    def test_low_score_for_normal_message(
        self, detector: FrustrationDetector,
    ) -> None:
        sig = detector.analyze("add a login button", history=[])
        assert sig.score < 0.3

    def test_high_score_for_repeated_complaint(
        self, detector: FrustrationDetector,
    ) -> None:
        sig = detector.analyze(
            "this is still broken why doesnt it work",
            history=[
                "fix the login page",
                "its not working",
                "still not working",
            ],
        )
        assert sig.score >= 0.7

    def test_escalation_language_boosts_score(
        self, detector: FrustrationDetector,
    ) -> None:
        base = detector.analyze("show me the results", history=[])
        escalated = detector.analyze(
            "still not showing the results again",
            history=["show me the results"],
        )
        assert escalated.score > base.score

    def test_rapid_resends_boost_score(
        self, detector: FrustrationDetector,
    ) -> None:
        now = time.time()
        sig = detector.analyze(
            "why is this broken",
            history=["fix it", "fix it now"],
            timestamps=[now - 20, now - 10, now],
        )
        assert sig.score >= 0.5

    def test_explicit_frustration_detected(
        self, detector: FrustrationDetector,
    ) -> None:
        sig = detector.analyze(
            "this is completely broken fix this now",
            history=[],
        )
        # Single frustrated message with no history is moderate
        assert sig.score >= 0.3
        assert sig.dimensions["explicit"] > 0


# ── Threshold actions ──────────────────────────────────────────────────


class TestThresholdActions:
    def test_low_score_action_is_log(
        self, detector: FrustrationDetector,
    ) -> None:
        sig = detector.analyze("hmm ok", history=["do something"])
        assert sig.action == "log"

    def test_high_score_action_is_notify(
        self, detector: FrustrationDetector,
    ) -> None:
        sig = detector.analyze(
            "this is BROKEN again nothing works",
            history=[
                "fix the page",
                "still broken",
                "why is it still broken",
            ],
        )
        assert sig.action in ("notify", "ticket")


# ── Edge cases ─────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_message(self, detector: FrustrationDetector) -> None:
        sig = detector.analyze("", history=[])
        assert sig.score == 0.0

    def test_none_history(self, detector: FrustrationDetector) -> None:
        sig = detector.analyze("hello", history=None)
        assert sig.score < 0.3

    def test_signal_is_dataclass(
        self, detector: FrustrationDetector,
    ) -> None:
        sig = detector.analyze("test", history=[])
        assert isinstance(sig, FrustrationSignal)
        assert hasattr(sig, "score")
        assert hasattr(sig, "target")
        assert hasattr(sig, "action")
