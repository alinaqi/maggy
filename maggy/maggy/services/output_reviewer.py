"""Inter-task output quality reviewer.

Sends step output to a fast local model for quality scoring.
Falls back to pass-through (score=3) on any failure so it
never blocks the pipeline.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maggy.adapters.pi import PiAdapter

logger = logging.getLogger(__name__)

_SCORE_RE = re.compile(r"SCORE:\s*(\d+)", re.IGNORECASE)
_REASON_RE = re.compile(r"REASON:\s*(.+)", re.IGNORECASE)

REVIEW_MODEL = "local"
REVIEW_MAX_TURNS = 1


@dataclass
class ReviewResult:
    score: int
    reason: str = ""


def _parse_review(text: str) -> ReviewResult:
    """Extract score and reason from reviewer output."""
    m = _SCORE_RE.search(text)
    if not m:
        return ReviewResult(score=3)
    score = max(1, min(5, int(m.group(1))))
    rm = _REASON_RE.search(text)
    reason = rm.group(1).strip() if rm else ""
    return ReviewResult(score=score, reason=reason)


def _build_prompt(step_label: str, output: str) -> str:
    """Build the review prompt for the local model."""
    trimmed = output[:3000]
    return (
        f"Review this {step_label} output for quality.\n"
        "Rate 1-5 (1=wrong, 3=acceptable, 5=excellent).\n"
        "Reply ONLY in this format:\n"
        "SCORE: <number>\nREASON: <one sentence>\n\n"
        f"--- OUTPUT ---\n{trimmed}"
    )


async def review_output(
    pi: "PiAdapter", step_label: str, output: str, wd: str,
) -> ReviewResult:
    """Send step output to local model for quality review."""
    prompt = _build_prompt(step_label, output)
    try:
        result = await pi.send_prompt(
            REVIEW_MODEL, prompt, wd,
            max_turns=REVIEW_MAX_TURNS, timeout=30,
        )
        if not result.success:
            return ReviewResult(score=3, reason="review unavailable")
        return _parse_review(result.output)
    except Exception as exc:
        logger.debug("Review failed: %s", exc)
        return ReviewResult(score=3, reason="review error")
