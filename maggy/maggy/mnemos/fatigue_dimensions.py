"""Full 4-dimension fatigue computation."""

from __future__ import annotations

from pathlib import Path

from maggy.mnemos.constants import (
    FATIGUE_WEIGHT_ERROR_DENSITY,
    FATIGUE_WEIGHT_REREAD_RATIO,
    FATIGUE_WEIGHT_SCOPE_SCATTER,
    FATIGUE_WEIGHT_TOKEN,
)
from maggy.mnemos.fatigue import estimate_token_util
from maggy.mnemos.signals import ToolSignal


def compute_scope_scatter(signals: list[ToolSignal]) -> float:
    """File path diversity. 0.0=one dir, 1.0=max scatter."""
    if not signals:
        return 0.0
    paths = [s.file_path for s in signals if s.file_path]
    if not paths:
        return 0.0
    dirs = {str(Path(p).parent) for p in paths}
    return min(len(dirs) / max(len(paths), 1), 1.0)


def compute_reread_ratio(signals: list[ToolSignal]) -> float:
    """Ratio of duplicate Read calls to total Reads."""
    reads = [
        s.file_path for s in signals
        if s.tool_name == "Read" and s.file_path
    ]
    if not reads:
        return 0.0
    unique = len(set(reads))
    return (len(reads) - unique) / len(reads)


def compute_error_density(signals: list[ToolSignal]) -> float:
    """Ratio of error outcomes to total signals."""
    if not signals:
        return 0.0
    errors = sum(1 for s in signals if s.outcome == "error")
    return min(errors / len(signals), 1.0)


def compute_all_dimensions(
    transcript: Path, signals: list[ToolSignal],
) -> dict[str, float]:
    """Return all 4 fatigue dimension values."""
    return {
        "token_util": estimate_token_util(transcript),
        "scope_scatter": compute_scope_scatter(signals),
        "reread_ratio": compute_reread_ratio(signals),
        "error_density": compute_error_density(signals),
    }


def composite_fatigue(dims: dict[str, float]) -> float:
    """Weighted sum of all 4 dimensions."""
    return (
        FATIGUE_WEIGHT_TOKEN * dims.get("token_util", 0)
        + FATIGUE_WEIGHT_SCOPE_SCATTER * dims.get("scope_scatter", 0)
        + FATIGUE_WEIGHT_REREAD_RATIO * dims.get("reread_ratio", 0)
        + FATIGUE_WEIGHT_ERROR_DENSITY * dims.get("error_density", 0)
    )
