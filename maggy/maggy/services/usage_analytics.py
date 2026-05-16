"""Cross-model usage analytics — aggregate stats across all providers.

Tracks token usage, cost, routing decisions, fatigue across every model
in the 9-tier stack. Answers "how are we doing across all models?"
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ModelUsage:
    model: str
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_est: float = 0.0
    avg_latency_ms: float = 0.0


@dataclass
class ProviderReport:
    period: str  # "today", "week", "month", "all"
    generated_at: str = ""
    models: list[ModelUsage] = field(default_factory=list)
    total_calls: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    savings_vs_claude: float = 0.0
    routing_decisions: int = 0
    top_classifier: str = ""
    sessions: int = 0
    fatigue_avg: float = 0.0
    fatigue_peak: float = 0.0


# Cost per 1M input tokens (for savings calculation)
MODEL_COSTS = {
    "qwen3": 0.0, "local": 0.0,
    "gemini-flash-lite": 0.10,
    "deepseek-flash": 0.14,
    "deepseek-pro": 0.44,
    "gemini-flash": 0.15,
    "kimi": 0.60,
    "gemini-pro-search": 1.25,
    "codex": 2.50,
    "claude": 3.00, "claude-sonnet": 3.00,
}
CLAUDE_COST = 3.00  # baseline for savings calc


def _load_routing_log() -> list[dict]:
    """Load all routing decisions from the log file."""
    path = Path.home() / ".claude" / "routing-log.jsonl"
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().strip().split("\n"):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries


def _load_buffer_usage() -> list[dict]:
    """Load post/engagement stats from build-in-public logs."""
    path = Path.home() / ".maggy" / "build-in-public" / "posts.jsonl"
    if not path.exists():
        return []
    entries = []
    for line in path.read_text().strip().split("\n"):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries


def generate_report(period: str = "today") -> ProviderReport:
    """Generate cross-model usage report for the given period."""
    now = datetime.now(timezone.utc)
    report = ProviderReport(period=period, generated_at=now.isoformat())

    # Time filter
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        from datetime import timedelta
        since = now - timedelta(days=7)
    elif period == "month":
        from datetime import timedelta
        since = now - timedelta(days=30)
    else:
        since = datetime(2020, 1, 1, tzinfo=timezone.utc)

    # 1. Routing decisions
    routing_log = _load_routing_log()
    decisions = [e for e in routing_log if _parse_ts(e.get("ts", "")) >= since]
    report.routing_decisions = len(decisions)

    # Classifier stats
    classifiers: dict[str, int] = {}
    for d in decisions:
        c = d.get("classifier", "unknown")
        classifiers[c] = classifiers.get(c, 0) + 1
    if classifiers:
        report.top_classifier = max(classifiers, key=classifiers.get)

    # Tier counts
    tier_counts: dict[str, int] = {}
    for d in decisions:
        tier = d.get("tier", "unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    # 2. Model usage aggregation
    model_usage: dict[str, ModelUsage] = {}
    for d in decisions:
        tier = d.get("tier", "unknown")
        model = tier.lower().replace("_", "-")
        if model not in model_usage:
            model_usage[model] = ModelUsage(model=model)

        mu = model_usage[model]
        mu.calls += 1
        # Estimate tokens from saved vs claude baseline
        saved = d.get("tokens_saved", 0) or 0
        estimated_tokens = saved * 2  # rough: saved tokens imply total
        mu.tokens_in += estimated_tokens
        mu.tokens_out += estimated_tokens // 4
        cost_per_m = MODEL_COSTS.get(model, 0.44)
        mu.cost_est += (estimated_tokens / 1_000_000) * cost_per_m

    report.models = sorted(model_usage.values(), key=lambda m: m.calls, reverse=True)
    report.total_calls = sum(m.calls for m in report.models)
    report.total_tokens = sum(m.tokens_in + m.tokens_out for m in report.models)
    report.total_cost = sum(m.cost_est for m in report.models)

    # 3. Savings vs pure Claude
    claude_cost = (report.total_tokens / 1_000_000) * CLAUDE_COST if report.total_tokens > 0 else 0
    report.savings_vs_claude = claude_cost - report.total_cost

    # 4. Buffer usage (build-in-public posts)
    buffer = _load_buffer_usage()
    report.sessions = len([b for b in buffer if _parse_ts(b.get("ts", "")) >= since]) if buffer else 0

    # 5. Fatigue tracking
    cache = Path.home() / ".claude" / "routing-cache.json"
    if cache.exists():
        try:
            c = json.loads(cache.read_text())
            # Fatigue not directly stored here, but we estimate from REM/PRE_SLEEP escalations
            rem_count = sum(1 for d in decisions if "REM" in str(d.get("tier", "")))
            escalate_count = sum(1 for d in decisions if "PRE_SLEEP" in str(d.get("tier", "")))
            if decisions:
                report.fatigue_avg = (rem_count * 0.8 + escalate_count * 0.6) / max(len(decisions), 1)
                report.fatigue_peak = 0.8 if rem_count > 0 else (0.6 if escalate_count > 0 else 0.2)
        except Exception:
            pass

    return report


def format_report(report: ProviderReport) -> str:
    """Format a report for CLI output."""
    lines = []
    w = 58
    lines.append("=" * w)
    lines.append(f"  📊 Cross-Model Usage — {report.period}")
    lines.append(f"  Generated: {report.generated_at[:19]}")
    lines.append("=" * w)
    lines.append("")
    lines.append(f"  Routing decisions: {report.routing_decisions}")
    lines.append(f"  Top classifier:    {report.top_classifier or 'unknown'}")
    lines.append(f"  Total cost (est):  ${report.total_cost:.4f}")
    lines.append(f"  Savings vs Claude: ${report.savings_vs_claude:.2f}")
    lines.append(f"  Fatigue avg/max:   {report.fatigue_avg:.2f} / {report.fatigue_peak:.2f}")

    if report.models:
        lines.append("")
        lines.append(f"  {'Model':<20s} {'Calls':>6s} {'Cost':>8s} {'%':>5s}")
        lines.append(f"  {'─'*20} {'─'*6} {'─'*8} {'─'*5}")
        total = report.total_calls
        for m in report.models:
            pct = f"{m.calls/total*100:.0f}%" if total > 0 else "0%"
            lines.append(f"  {m.model:<20s} {m.calls:>6d} ${m.cost_est:>7.4f} {pct:>5s}")

    lines.append("")
    return "\n".join(lines)


def _parse_ts(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime(2020, 1, 1, tzinfo=timezone.utc)
