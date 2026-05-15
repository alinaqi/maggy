"""Backward-compatible APIs from Mnemos v0 stubs."""

from __future__ import annotations

import json
from pathlib import Path

VALID_DIMENSIONS = frozenset({
    "context_load",
    "turn_pressure",
    "reread_ratio",
    "handoff_risk",
})


class FatigueTracker:
    """Track fatigue across four compression signals."""

    def __init__(self, context_window: int = 200_000):
        self.context_window = context_window
        self.dimensions: dict[str, float] = {
            d: 0.0 for d in VALID_DIMENSIONS
        }

    def record(self, dimension: str, value: float) -> None:
        if dimension not in VALID_DIMENSIONS:
            raise ValueError(
                f"Unknown dimension {dimension!r}. "
                f"Valid: {sorted(VALID_DIMENSIONS)}"
            )
        self.dimensions[dimension] = max(0.0, min(value, 1.0))

    def on_model_switch(self, new_context_window: int) -> None:
        self.context_window = new_context_window
        value = self.dimensions["reread_ratio"] + 0.15
        self.record("reread_ratio", value)

    def composite(self) -> float:
        return sum(self.dimensions.values()) / len(self.dimensions)

    def state(self) -> str:
        score = self.composite()
        if score >= 0.8:
            return "critical"
        if score >= 0.45:
            return "compress"
        return "ok"


class SignalLog:
    """Append and read Mnemos signal history."""

    def __init__(self, path: Path):
        self._path = path

    def append(self, signal: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(signal) + "\n")

    def recent(self, n: int) -> list[dict]:
        if n <= 0 or not self._path.exists():
            return []
        from collections import deque
        with self._path.open(encoding="utf-8") as handle:
            lines = deque(handle, maxlen=n)
        return [json.loads(line) for line in lines]
