"""JSONL signal logger for tool call tracking."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from maggy.mnemos.constants import SIGNALS_FILENAME


@dataclass(frozen=True)
class ToolSignal:
    """Immutable record of a tool invocation."""

    timestamp: str
    tool_name: str
    file_path: str = ""
    outcome: str = "success"
    duration_ms: int = 0
    metadata: dict = field(default_factory=dict)


def append_signal(mnemos_dir: Path, signal: ToolSignal) -> None:
    """Append one JSONL line. Fails silently on I/O error."""
    try:
        path = mnemos_dir / SIGNALS_FILENAME
        with path.open("a") as f:
            f.write(json.dumps(asdict(signal)) + "\n")
    except OSError:
        pass


def read_signals(mnemos_dir: Path) -> list[ToolSignal]:
    """Read all signals from JSONL."""
    path = mnemos_dir / SIGNALS_FILENAME
    if not path.exists():
        return []
    signals: list[ToolSignal] = []
    for line in path.read_text().splitlines():
        try:
            d = json.loads(line)
            signals.append(_dict_to_signal(d))
        except (json.JSONDecodeError, TypeError):
            continue
    return signals


def read_recent_signals(
    mnemos_dir: Path, n: int = 30,
) -> list[ToolSignal]:
    """Read the last *n* signals without loading full file."""
    path = mnemos_dir / SIGNALS_FILENAME
    if n <= 0 or not path.exists():
        return []
    from collections import deque

    signals: list[ToolSignal] = []
    with path.open(encoding="utf-8") as fh:
        for line in deque(fh, maxlen=n):
            try:
                signals.append(_dict_to_signal(json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                continue
    return signals


def read_signals_since(
    mnemos_dir: Path, since: datetime,
) -> list[ToolSignal]:
    """Read signals newer than `since`."""
    cutoff = since.isoformat()
    return [
        s for s in read_signals(mnemos_dir)
        if s.timestamp >= cutoff
    ]


def count_signals_by_tool(
    signals: list[ToolSignal],
) -> dict[str, int]:
    """Aggregate signal count per tool_name."""
    counts: dict[str, int] = {}
    for s in signals:
        counts[s.tool_name] = counts.get(s.tool_name, 0) + 1
    return counts


def extract_file_paths(
    signals: list[ToolSignal],
) -> list[str]:
    """Extract unique file paths from signals."""
    seen: set[str] = set()
    result: list[str] = []
    for s in signals:
        if s.file_path and s.file_path not in seen:
            seen.add(s.file_path)
            result.append(s.file_path)
    return result


def signal_from_hook_data(data: dict) -> ToolSignal:
    """Parse a ToolSignal from hook JSON stdin."""
    now = datetime.now(timezone.utc).isoformat()
    return ToolSignal(
        timestamp=data.get("timestamp", now),
        tool_name=data.get("tool_name", "unknown"),
        file_path=data.get("file_path", ""),
        outcome=data.get("outcome", "success"),
    )


def _dict_to_signal(d: dict) -> ToolSignal:
    return ToolSignal(
        timestamp=d.get("timestamp", ""),
        tool_name=d.get("tool_name", ""),
        file_path=d.get("file_path", ""),
        outcome=d.get("outcome", "success"),
        duration_ms=d.get("duration_ms", 0),
        metadata=d.get("metadata", {}),
    )
