"""Dual-model planning orchestrator.

Generates plan with primary model, counter-checks with secondary,
merges into a diff showing agreements and conflicts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from maggy.config import MaggyConfig
from maggy.models.plan import Plan, PlanDiff, PlanStep

logger = logging.getLogger(__name__)

DUAL_PLAN_THRESHOLD = 4


@dataclass
class PlanRequest:
    """Input for plan generation."""

    task: str
    blast_score: int = 0
    file_context: list[str] | None = None


class PlanningService:
    """Dual-plan orchestrator."""

    def __init__(self, cfg: MaggyConfig):
        self.cfg = cfg

    def should_dual_plan(self, blast_score: int) -> bool:
        """Only dual-plan for tasks above threshold."""
        return blast_score >= DUAL_PLAN_THRESHOLD

    def generate_plan(
        self, task: str, model: str,
        files: list[str] | None = None,
    ) -> Plan:
        """Generate a plan (stub — real impl calls LLM)."""
        steps = [
            PlanStep(
                description=f"Analyze {task}",
                files=files or [],
                blast_estimate=1,
            ),
            PlanStep(
                description=f"Implement {task}",
                files=files or [],
                blast_estimate=2,
            ),
            PlanStep(
                description=f"Test {task}",
                blast_estimate=1,
            ),
        ]
        return Plan(
            task=task, model=model, steps=steps,
            total_blast=sum(s.blast_estimate for s in steps),
        )

    def diff_plans(
        self, primary: Plan, counter: Plan,
    ) -> PlanDiff:
        """Compare two plans and produce a diff."""
        p_descs = {s.description for s in primary.steps}
        c_descs = {s.description for s in counter.steps}

        agreed = list(p_descs & c_descs)
        primary_only = list(p_descs - c_descs)
        counter_only = list(c_descs - p_descs)

        conflicts = []
        for po in primary_only:
            for co in counter_only:
                if _similar(po, co):
                    conflicts.append({
                        "primary": po, "counter": co,
                    })

        return PlanDiff(
            agreed=agreed,
            conflicts=conflicts,
            primary_only=[
                p for p in primary_only
                if not any(c["primary"] == p for c in conflicts)
            ],
            counter_only=[
                c for c in counter_only
                if not any(cf["counter"] == c for cf in conflicts)
            ],
        )

    def plan_task(self, req: PlanRequest) -> dict:
        """Full planning flow for a task."""
        primary = self.generate_plan(
            req.task, "claude", req.file_context,
        )
        if not self.should_dual_plan(req.blast_score):
            return {
                "mode": "single",
                "plan": primary,
                "diff": None,
            }

        counter = self.generate_plan(
            req.task, "codex", req.file_context,
        )
        diff = self.diff_plans(primary, counter)
        return {
            "mode": "dual",
            "plan": primary,
            "counter_plan": counter,
            "diff": diff,
        }


def _similar(a: str, b: str) -> bool:
    """Simple word-overlap similarity check."""
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return False
    overlap = len(a_words & b_words)
    return overlap / min(len(a_words), len(b_words)) > 0.5
