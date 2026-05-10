"""Blast-to-model routing with iCPG integration and reward learning.

Routes tasks to the optimal model based on complexity score.
High-blast tasks go to premium models, low-blast to cheap ones.
Learns from reward scores over time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from maggy.config import MaggyConfig
from maggy.process.model_router import (
    DEFAULT_TIERS,
    RoutingDecision,
    route_task,
)
from maggy.scores import RewardTable


@dataclass
class RoutingContext:
    """Input context for a routing decision."""

    blast_score: int = 0
    task_type: str = "general"
    security_sensitive: bool = False
    project_key: str = ""


class RoutingService:
    """Blast-score aware routing with reward-based learning."""

    def __init__(self, cfg: MaggyConfig):
        self.cfg = cfg
        self.rewards = RewardTable(cfg)

    def route(self, ctx: RoutingContext) -> RoutingDecision:
        """Pick the best model for this task context."""
        # Check reward table for learned preferences
        override = self.rewards.best_model(
            ctx.task_type, self._blast_tier(ctx.blast_score),
        )
        if override:
            return RoutingDecision(
                primary=override,
                validator=None,
                fallback_chain=[],
                reason=f"Learned: best for {ctx.task_type} "
                       f"at blast {ctx.blast_score}",
            )

        return route_task(
            ctx.blast_score,
            ctx.task_type,
            ctx.security_sensitive,
        )

    def record_outcome(
        self,
        model: str,
        task_type: str,
        blast_score: int,
        reward: float,
    ) -> None:
        """Record task outcome for learning."""
        tier = self._blast_tier(blast_score)
        self.rewards.record(model, task_type, tier, reward)

    def get_heatmap(self) -> list[dict]:
        """Return reward heatmap data for dashboard."""
        return self.rewards.heatmap()

    def _blast_tier(self, score: int) -> str:
        if score <= 3:
            return "low"
        if score <= 6:
            return "medium"
        return "high"
