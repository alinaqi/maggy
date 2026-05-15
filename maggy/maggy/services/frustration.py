"""Frustration detection service.

Analyzes chat messages for user frustration signals,
classifies the frustration *target* (app bug vs output
quality vs task difficulty), and recommends an action.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class FrustrationTarget(str, Enum):
    APP_BUG = "app_bug"
    OUTPUT_QUALITY = "output_quality"
    TASK_DIFFICULTY = "task_difficulty"
    NONE = "none"


@dataclass(frozen=True)
class FrustrationSignal:
    score: float
    target: FrustrationTarget
    action: str
    dimensions: dict[str, float] = field(
        default_factory=dict,
    )


# ── Keyword patterns ──────────────────────────────────────────────────

_APP_BUG = re.compile(
    r"\b(refresh|page|button|click|load|show|display|render"
    r"|blank|empty|nothing|404|crash|screen)\b",
    re.IGNORECASE,
)
_OUTPUT_QUALITY = re.compile(
    r"\b(wrong|meant|asked|said|not what|answer|response"
    r"|output|result|told you|already said|I said"
    r"|not\s+\w+|as\s+(?:black|white))\b",
    re.IGNORECASE,
)
_TASK_DIFFICULTY = re.compile(
    r"\b(nevermind|never mind|forget it|something else"
    r"|dont know|don'?t know|confused|actually|skip)\b",
    re.IGNORECASE,
)
_ESCALATION = re.compile(
    r"\b(still|again|not working|why doesn'?t|broken"
    r"|keeps|same|every time|always)\b",
    re.IGNORECASE,
)
_EXPLICIT = re.compile(
    r"\b(broken|fix\s+this|doesn'?t work|useless"
    r"|terrible|awful|stupid|hate|completely\s+\w+)\b",
    re.IGNORECASE,
)

# Weights from the RFC
_W_REPETITION = 0.30
_W_ESCALATION = 0.25
_W_RAPID = 0.20
_W_EXPLICIT = 0.15
_W_ABANDON = 0.10

_RAPID_WINDOW = 60.0  # seconds
_RAPID_THRESHOLD = 3


class FrustrationDetector:
    """Stateless frustration analyzer."""

    def analyze(
        self,
        message: str,
        *,
        history: Sequence[str] | None = None,
        timestamps: Sequence[float] | None = None,
    ) -> FrustrationSignal:
        if not message:
            return FrustrationSignal(
                score=0.0,
                target=FrustrationTarget.NONE,
                action="log",
            )
        hist = list(history or [])
        target = self._classify_target(message, hist)
        dims = self._score_dimensions(
            message, hist, timestamps,
        )
        score = sum(dims.values())
        score = min(max(score, 0.0), 1.0)
        action = _action_for_score(score)
        return FrustrationSignal(
            score=round(score, 3),
            target=target,
            action=action,
            dimensions=dims,
        )

    def _classify_target(
        self, msg: str, history: list[str],
    ) -> FrustrationTarget:
        combined = " ".join([*history[-3:], msg]).lower()
        app = len(_APP_BUG.findall(combined))
        out = len(_OUTPUT_QUALITY.findall(combined))
        diff = len(_TASK_DIFFICULTY.findall(combined))
        if app == 0 and out == 0 and diff == 0:
            return FrustrationTarget.NONE
        scores = {
            FrustrationTarget.APP_BUG: app,
            FrustrationTarget.OUTPUT_QUALITY: out,
            FrustrationTarget.TASK_DIFFICULTY: diff,
        }
        return max(scores, key=scores.get)  # type: ignore[arg-type]

    def _score_dimensions(
        self,
        msg: str,
        history: list[str],
        timestamps: Sequence[float] | None,
    ) -> dict[str, float]:
        dims: dict[str, float] = {}
        dims["repetition"] = _W_REPETITION * _repetition(
            msg, history,
        )
        dims["escalation"] = _W_ESCALATION * _escalation(msg)
        dims["rapid"] = _W_RAPID * _rapid_sends(timestamps)
        dims["explicit"] = _W_EXPLICIT * _explicit(msg)
        dims["abandon"] = _W_ABANDON * _abandonment(
            msg, history,
        )
        # Convergence bonus: multiple active dimensions
        # amplify the signal
        active = sum(1 for v in dims.values() if v > 0)
        if active >= 2:
            dims = {k: v * (1 + 0.2 * active) for k, v in dims.items()}
        return dims


def _repetition(msg: str, history: list[str]) -> float:
    if not history:
        return 0.0
    msg_words = set(msg.lower().split())
    best = 0.0
    for prev in reversed(history[-3:]):
        prev_words = set(prev.lower().split())
        if not prev_words:
            continue
        overlap = len(msg_words & prev_words)
        ratio = overlap / max(len(prev_words), 1)
        best = max(best, ratio)
    # Also check if escalation words appear alongside
    # history overlap — stronger signal
    if best > 0.2 and _ESCALATION.search(msg):
        best = min(best + 0.4, 1.0)
    if best > 0.3:
        return min(best * 1.5, 1.0)
    return 0.0


def _escalation(msg: str) -> float:
    hits = len(_ESCALATION.findall(msg))
    return min(hits / 2.0, 1.0)


def _rapid_sends(
    timestamps: Sequence[float] | None,
) -> float:
    if not timestamps or len(timestamps) < _RAPID_THRESHOLD:
        return 0.0
    recent = sorted(timestamps)[-_RAPID_THRESHOLD:]
    span = recent[-1] - recent[0]
    if span <= _RAPID_WINDOW:
        return 1.0
    return 0.0


def _explicit(msg: str) -> float:
    hits = len(_EXPLICIT.findall(msg))
    return min(hits / 2.0, 1.0)


def _abandonment(msg: str, history: list[str]) -> float:
    if _TASK_DIFFICULTY.search(msg):
        return 1.0
    if len(history) >= 3:
        topics = {m.split()[0].lower() for m in history[-3:] if m}
        current = msg.split()[0].lower() if msg else ""
        if current and current not in topics:
            return 0.5
    return 0.0


def _action_for_score(score: float) -> str:
    if score >= 0.9:
        return "ticket"
    if score >= 0.7:
        return "notify"
    if score >= 0.5:
        return "adjust"
    return "log"
