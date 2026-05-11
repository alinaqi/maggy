"""Blast-to-model routing with iCPG integration and reward learning.

Routes tasks to the optimal model based on complexity score.
High-blast tasks go to premium models, low-blast to cheap ones.
Learns from reward scores over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from maggy.calibration.tracker import CalibrationTracker
from maggy.config import MaggyConfig
from maggy.process.model_router import (
    RoutingDecision,
    route_task,
)
from maggy.scores import RewardTable

MIN_CALIBRATION_ACCURACY = 0.5


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
        db_dir = Path(cfg.storage.path).expanduser().parent
        self.calibration = CalibrationTracker(db_dir / "calibration.db")

    def route(self, ctx: RoutingContext) -> RoutingDecision:
        """Pick the best model for this task context."""
        override = self.rewards.best_model(
            ctx.task_type, self._blast_tier(ctx.blast_score),
        )
        if override and self._is_calibrated(override):
            return RoutingDecision(
                primary=override,
                validator=None,
                fallback_chain=[],
                reason=f"Learned: best for {ctx.task_type} "
                       f"at blast {ctx.blast_score}",
            )

        decision = route_task(
            ctx.blast_score,
            ctx.task_type,
            ctx.security_sensitive,
        )
        return self._penalize_uncalibrated(decision)

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
        self.calibration.record(model, task_type, reward, reward)

    def get_heatmap(self) -> list[dict]:
        """Return reward heatmap data for dashboard."""
        return self.rewards.heatmap()

    def _blast_tier(self, score: int) -> str:
        if score <= 3:
            return "low"
        if score <= 6:
            return "medium"
        return "high"

    def _is_calibrated(self, model: str) -> bool:
        acc = self.calibration.accuracy(model)
        return acc == 0.0 or acc >= MIN_CALIBRATION_ACCURACY

    def _penalize_uncalibrated(
        self, decision: RoutingDecision,
    ) -> RoutingDecision:
        if not self._is_calibrated(decision.primary.name):
            chain = decision.fallback_chain
            if chain:
                return RoutingDecision(
                    primary=chain[0],
                    validator=decision.validator,
                    fallback_chain=chain[1:],
                    reason="Calibration penalty",
                )
        return decision
