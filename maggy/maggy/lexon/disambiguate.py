"""Confidence-gated disambiguation for ambiguous intents."""

from __future__ import annotations

from dataclasses import dataclass

SELF_CLARIFY_THRESHOLD = 0.5
USER_CLARIFY_THRESHOLD = 0.3


@dataclass
class DisambiguationResult:
    """Outcome of disambiguation attempt."""

    resolved: bool
    tool: str = ""
    mode: str = ""  # self_clarify | user_clarify | none
    suggestions: list[str] | None = None


def disambiguate(
    confidence: float,
    candidates: list[str],
) -> DisambiguationResult:
    """Determine disambiguation strategy.

    >= 0.7: auto-resolve (no disambiguation needed)
    0.5-0.7: self-clarify (use context to pick)
    0.3-0.5: user-clarify (ask the user)
    < 0.3: reject (too ambiguous)
    """
    if confidence >= 0.7 and candidates:
        return DisambiguationResult(
            resolved=True, tool=candidates[0], mode="none",
        )

    if confidence >= SELF_CLARIFY_THRESHOLD and candidates:
        return DisambiguationResult(
            resolved=True, tool=candidates[0],
            mode="self_clarify",
            suggestions=candidates[:3],
        )

    if confidence >= USER_CLARIFY_THRESHOLD and candidates:
        return DisambiguationResult(
            resolved=False, mode="user_clarify",
            suggestions=candidates[:5],
        )

    return DisambiguationResult(
        resolved=False, mode="none",
        suggestions=candidates[:3] if candidates else None,
    )
