"""Model budget tracking — daily spend estimation from routing log."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

MODEL_DAILY_BUDGETS: dict[str, float] = {
    "claude": 2.00,
    "claude-opus": 3.00,
    "gemini-pro-search": 1.00,
    "gemini-3.5-flash": 1.50,
    "codex": 1.50,
    "kimi": 0.50,
}

BUDGET_WARN_THRESHOLD = 0.5
BUDGET_BLOCK_THRESHOLD = 0.8

_RATES: dict[str, float] = {
    "claude": 3.0, "claude-opus": 5.0, "codex": 2.5,
    "gemini-pro-search": 1.25, "gemini-3.5-flash": 1.5,
    "kimi": 0.6, "deepseek-pro": 0.44, "gemini-flash": 0.15,
    "deepseek-flash": 0.14, "gemini-flash-lite": 0.10,
    "grok": 1.25,
}


def get_model_usage_today() -> dict[str, float]:
    path = Path.home() / ".claude" / "routing-log.jsonl"
    if not path.exists():
        return {}
    now = datetime.now(timezone.utc)
    since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    usage: dict[str, float] = {}
    for line in path.read_text().strip().split("\n"):
        try:
            entry = json.loads(line)
            ts = entry.get("ts", "")
            ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts_dt < since:
                continue
            tier = entry.get("tier", "").lower().replace("_", "-")
            saved = entry.get("tokens_saved", 0) or 0
            est_tokens = saved * 2
            rate = _RATES.get(tier, 0.44)
            usage[tier] = usage.get(tier, 0.0) + (est_tokens / 1_000_000) * rate
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return usage
