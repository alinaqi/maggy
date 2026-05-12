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
    DEFAULT_TIERS,
    RoutingDecision,
    route_task,
)
from maggy.routing_rules import apply_override
from maggy.routing_rules_io import load as load_rules
from maggy.routing_rules import record_outcome as rules_record
from maggy.scores import RewardTable

MIN_CALIBRATION_ACCURACY = 0.5


@dataclass
class RoutingContext:
    """Input context for a routing decision."""

    blast_score: int = 0
    task_type: str = "general"
    security_sensitive: bool = False
    project_key: str = ""
    pipeline_phase: str = ""
    stakes: str = "low"


class RoutingService:
    """Blast-score aware routing with rule overrides."""

    def __init__(self, cfg: MaggyConfig):
        self.cfg = cfg
        self.rewards = RewardTable(cfg)
        db_dir = Path(cfg.storage.path).expanduser().parent
        self.calibration = CalibrationTracker(
            db_dir / "calibration.db",
        )
        self.rules = load_rules()

    def route(self, ctx: RoutingContext) -> RoutingDecision:
        """Pick the best model for this task context."""
        forced = apply_override(
            self.rules, ctx.task_type, ctx.pipeline_phase,
        )
        if forced:
            return self._forced_decision(forced, ctx)

        override = self.rewards.best_model(
            ctx.task_type, self._blast_tier(ctx.blast_score),
        )
        if override and self._is_calibrated(override):
            return RoutingDecision(
                primary=override,
                validator=None,
                fallback_chain=[],
                reason=(
                    f"Learned: best for {ctx.task_type} "
                    f"at blast {ctx.blast_score}"
                ),
            )

        decision = route_task(
            ctx.blast_score,
            ctx.task_type,
            ctx.security_sensitive,
            stakes=ctx.stakes,
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
        success = reward > 0.0
        rules_record(self.rules, model, task_type, success)

    def reload_rules(self) -> None:
        """Reload rules from disk (after Maggy self-update)."""
        self.rules = load_rules()

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

    def _forced_decision(
        self, model_name: str, ctx: RoutingContext,
    ) -> RoutingDecision:
        """Build decision from a rules override."""
        tier = _find_tier(model_name)
        if tier is None:
            return route_task(
                ctx.blast_score,
                ctx.task_type,
                ctx.security_sensitive,
                stakes=ctx.stakes,
            )
        validator = None
        if ctx.blast_score >= 8 or ctx.security_sensitive or ctx.stakes == "high":
            validator = _find_tier("codex")
        return RoutingDecision(
            primary=tier,
            validator=validator,
            fallback_chain=[],
            reason=f"Rule override: {ctx.task_type}"
                   f"{f'/{ctx.pipeline_phase}' if ctx.pipeline_phase else ''}"
                   f" → {model_name}",
        )

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


def _find_tier(name: str):
    """Look up a ModelTier by name from defaults."""
    for t in DEFAULT_TIERS:
        if t.name == name:
            return t
    return None
