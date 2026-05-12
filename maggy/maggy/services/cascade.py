"""Cascade execution — quality-gate-based model escalation.

Try cheapest model first, evaluate output quality, escalate
to next tier if quality gate fails. Max 3 attempts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from maggy.adapters.pi import PiAdapter

logger = logging.getLogger(__name__)


@dataclass
class CascadeAttempt:
    """Record of a single cascade attempt."""

    model: str
    success: bool
    score: int = 0
    output: str = ""
    cost_usd: float = 0.0


@dataclass
class CascadeResult:
    """Result of cascade execution."""

    model: str
    output: str
    attempts: list[CascadeAttempt] = field(default_factory=list)
    escalated: bool = False
    cost_usd: float = 0.0


async def cascade_execute(
    pi: PiAdapter,
    chain: list[str],
    prompt: str,
    wd: str,
    quality_gate: Callable[[str], int],
) -> CascadeResult:
    """Try cheapest model, escalate on quality gate failure."""
    attempts: list[CascadeAttempt] = []
    best = CascadeAttempt("", False)
    max_attempts = min(len(chain), 3)

    for i in range(max_attempts):
        model = chain[i]
        result = await pi.send_prompt(model, prompt, wd)
        cost = getattr(result, "cost_usd", 0.0)
        if not result.success:
            attempts.append(CascadeAttempt(model, False))
            logger.info("Cascade: %s failed, escalating", model)
            continue
        score = await quality_gate(result.output)
        attempt = CascadeAttempt(model, True, score, result.output, cost)
        attempts.append(attempt)
        if score > best.score:
            best = attempt
        if score >= 3:
            return CascadeResult(
                model, result.output, attempts,
                escalated=i > 0, cost_usd=cost,
            )
        logger.info(
            "Cascade: %s scored %d, escalating", model, score,
        )

    return CascadeResult(
        best.model, best.output, attempts,
        escalated=len(attempts) > 1,
        cost_usd=best.cost_usd,
    )
