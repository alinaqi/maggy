"""Fatigue computation — Tier 0 (token) and full 4-dim."""

from __future__ import annotations

import json
from pathlib import Path

from maggy.mnemos.constants import (
    FATIGUE_FILENAME,
    FATIGUE_WEIGHT_TOKEN,
    TRANSCRIPT_FULL_BYTES,
)
from maggy.mnemos.models import FatigueState


def estimate_token_util(transcript: Path) -> float:
    """Estimate token utilization from file size."""
    if not transcript.exists():
        return 0.0
    size = transcript.stat().st_size
    return min(size / TRANSCRIPT_FULL_BYTES, 1.0)


def compute_fatigue(
    transcript: Path,
    signals: list | None = None,
) -> FatigueState:
    """Compute fatigue. signals=None -> Tier 0 only."""
    if signals is not None:
        return _compute_full(transcript, signals)
    util = estimate_token_util(transcript)
    score = FATIGUE_WEIGHT_TOKEN * util
    return FatigueState(score=score, token_util=util)


def _compute_full(
    transcript: Path, signals: list,
) -> FatigueState:
    from maggy.mnemos.fatigue_dimensions import (
        composite_fatigue,
        compute_all_dimensions,
    )

    dims = compute_all_dimensions(transcript, signals)
    score = composite_fatigue(dims)
    return FatigueState(
        score=score,
        token_util=dims["token_util"],
        scope_scatter=dims["scope_scatter"],
        reread_ratio=dims["reread_ratio"],
        error_density=dims["error_density"],
    )


def save_fatigue(mnemos_dir: Path, fs: FatigueState) -> None:
    """Persist fatigue state to JSON."""
    path = mnemos_dir / FATIGUE_FILENAME
    data = {
        "score": fs.score,
        "token_util": fs.token_util,
        "state": fs.state,
        "measured_at": fs.measured_at.isoformat(),
    }
    path.write_text(json.dumps(data, indent=2))


def load_fatigue(mnemos_dir: Path) -> FatigueState | None:
    """Load persisted fatigue state."""
    path = mnemos_dir / FATIGUE_FILENAME
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return FatigueState(
        score=data["score"],
        token_util=data["token_util"],
    )
