"""Error pattern learner — track error classes and recovery outcomes."""

from __future__ import annotations

from datetime import datetime, timezone


def build_error_signal(
    error_class: str,
    error_content: str,
    recovery_succeeded: bool,
) -> dict:
    return {
        "memory_type": "fact",
        "content": (
            f"Error [{error_class}]: {error_content[:150]}. "
            f"Recovery: {'succeeded' if recovery_succeeded else 'failed'}. "
            f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        ),
        "tags": [
            "error-pattern",
            f"class:{error_class}",
            "recovered" if recovery_succeeded else "unrecovered",
        ],
        "confidence": 1.0,
    }
