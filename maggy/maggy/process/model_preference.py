"""Read the shared followed-model preference (~/.claude/model-config.json).

This is the same source of truth used by srooter and the route-task hooks,
so Maggy follows whatever primary model the user picked at onboarding.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG = Path.home() / ".claude" / "model-config.json"

# Logical name in the shared config -> Maggy model name (see adapters/pi.py).
_ALIAS = {
    "qwen": "local",
    "minimax": "minimax",
    "claude": "claude",
    "deepseek": "deepseek-pro",
    "kimi": "kimi",
    "grok": "grok",
    "gemini": "gemini-flash",
    "codex": "codex",
}


def followed_model(path: Path = CONFIG, known: set[str] | None = None) -> str | None:
    """Return the user's followed model as a Maggy model name, or None.

    None means "no preference / unknown model" — callers keep their default.
    """
    try:
        primary = json.loads(path.read_text()).get("primary")
    except (OSError, ValueError):
        return None
    if not primary:
        return None
    name = _ALIAS.get(primary, primary)
    if known is None:
        from maggy.adapters.pi import DEFAULT_MODELS
        known = {m.name for m in DEFAULT_MODELS}
    return name if name in known else None
