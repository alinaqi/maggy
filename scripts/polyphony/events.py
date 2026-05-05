"""Structured event parsing from container stdout (§8 events).

Parses NDJSON and stream-json output into TaskEvent objects.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TaskEvent:
    """A single parsed event from agent output."""

    kind: str
    data: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=_now)

    @classmethod
    def from_dict(cls, d: dict) -> TaskEvent:
        """Create from a dictionary."""
        return cls(
            kind=d.get("kind", "unknown"),
            data=d.get("data", {}),
            timestamp=d.get("timestamp", _now()),
        )


def parse_ndjson_line(line: str) -> dict | None:
    """Parse a single NDJSON line. Returns None on failure."""
    stripped = line.strip()
    if not stripped:
        return None
    try:
        return json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return None


def parse_stream_json(lines: list[str]) -> list[dict]:
    """Parse multiple NDJSON lines, skipping invalid ones."""
    results: list[dict] = []
    for line in lines:
        parsed = parse_ndjson_line(line)
        if parsed is not None:
            results.append(parsed)
    return results


def classify_event(data: dict) -> TaskEvent:
    """Classify a parsed JSON object into a TaskEvent."""
    event_type = data.get("type", "unknown")
    return TaskEvent(kind=event_type, data=data)
