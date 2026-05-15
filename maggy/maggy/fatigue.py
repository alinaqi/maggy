"""Model-normalized fatigue tracking for cross-model sessions.

Normalizes fatigue scores across models with different context windows
so that 0.6 means "approaching limit" regardless of model.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FatigueProfile:
    """Fatigue state for a model during a session."""

    model: str
    context_window: int
    tokens_used: int = 0
    turns: int = 0
    recovery_reads: int = 0

    @property
    def raw_utilization(self) -> float:
        """Raw context utilization 0.0-1.0."""
        if self.context_window <= 0:
            return 0.0
        return min(self.tokens_used / self.context_window, 1.0)

    @property
    def fatigue_score(self) -> float:
        """Normalized fatigue score 0.0-1.0.

        Combines context utilization with turn-based fatigue.
        Higher = more fatigued.
        """
        ctx_factor = self.raw_utilization
        turn_factor = min(self.turns / 50.0, 1.0)
        return min(ctx_factor * 0.7 + turn_factor * 0.3, 1.0)

    def should_checkpoint(self, threshold: float = 0.6) -> bool:
        """Whether the model should checkpoint soon."""
        return self.fatigue_score >= threshold


MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "claude": 200_000,
    "gpt": 128_000,
    "kimi": 128_000,
    "deepseek-flash": 128_000,
    "deepseek-pro": 128_000,
    "codex": 200_000,
    "local": 32_000,
}


def create_profile(model: str) -> FatigueProfile:
    """Create a fatigue profile for a known model."""
    window = MODEL_CONTEXT_WINDOWS.get(model, 128_000)
    return FatigueProfile(model=model, context_window=window)


def compare_fatigue(
    profiles: list[FatigueProfile],
) -> list[dict]:
    """Compare fatigue across active models."""
    return [
        {
            "model": p.model,
            "fatigue": round(p.fatigue_score, 3),
            "utilization": round(p.raw_utilization, 3),
            "turns": p.turns,
            "should_checkpoint": p.should_checkpoint(),
        }
        for p in sorted(
            profiles, key=lambda p: p.fatigue_score, reverse=True,
        )
    ]
