"""Aggregation and pattern detection for session history."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from .models import (
    HistoryReport,
    ProjectActivity,
    ProviderUsage,
    SessionEntry,
    TimeDistribution,
    _now_iso,
)


def build_report(
    sessions: list[SessionEntry],
) -> HistoryReport:
    """Build complete history report from sessions."""
    if not sessions:
        return HistoryReport(
            generated_at=_now_iso(),
            total_sessions=0,
            total_prompts=0,
        )
    return HistoryReport(
        generated_at=_now_iso(),
        total_sessions=len(sessions),
        total_prompts=sum(s.prompt_count for s in sessions),
        providers=aggregate_by_provider(sessions),
        projects=aggregate_by_project(sessions),
        time_distribution=compute_time_distribution(sessions),
        top_topics=extract_top_topics(sessions),
        patterns=detect_patterns(sessions),
    )


def aggregate_by_provider(
    sessions: list[SessionEntry],
) -> list[ProviderUsage]:
    """Group sessions by provider."""
    by_prov: dict[str, list[SessionEntry]] = defaultdict(list)
    for s in sessions:
        by_prov[s.provider].append(s)

    result: list[ProviderUsage] = []
    for prov, items in sorted(by_prov.items()):
        minutes = sum(
            s.duration_minutes or 0 for s in items
        )
        models: set[str] = set()
        for s in items:
            models.update(s.models_used)
        result.append(ProviderUsage(
            provider=prov,
            session_count=len(items),
            prompt_count=sum(s.prompt_count for s in items),
            total_minutes=minutes,
            models_used=sorted(models),
        ))
    return result


def aggregate_by_project(
    sessions: list[SessionEntry],
) -> list[ProjectActivity]:
    """Group sessions by project."""
    by_proj: dict[str, list[SessionEntry]] = defaultdict(list)
    for s in sessions:
        by_proj[s.project].append(s)

    result: list[ProjectActivity] = []
    for proj, items in sorted(by_proj.items()):
        providers = sorted({s.provider for s in items})
        dates = [s.started_at for s in items if s.started_at]
        date_range = (min(dates), max(dates)) if dates else ("", "")
        topics = _merge_topics(items)
        result.append(ProjectActivity(
            project=proj,
            total_sessions=len(items),
            total_prompts=sum(s.prompt_count for s in items),
            providers_used=providers,
            date_range=date_range,
            top_topics=topics[:5],
        ))
    return result


def compute_time_distribution(
    sessions: list[SessionEntry],
) -> TimeDistribution:
    """Bucket sessions by hour, weekday, date."""
    by_hour: Counter[int] = Counter()
    by_weekday: Counter[int] = Counter()
    by_date: Counter[str] = Counter()

    for s in sessions:
        if not s.started_at:
            continue
        try:
            dt = datetime.fromisoformat(s.started_at)
        except ValueError:
            continue
        by_hour[dt.hour] += 1
        by_weekday[dt.weekday()] += 1
        by_date[dt.strftime("%Y-%m-%d")] += s.prompt_count

    return TimeDistribution(
        by_hour=dict(by_hour),
        by_weekday=dict(by_weekday),
        by_date=dict(by_date),
    )


def extract_top_topics(
    sessions: list[SessionEntry],
) -> list[str]:
    """Frequency-rank topics across all sessions."""
    counts: Counter[str] = Counter()
    for s in sessions:
        for t in s.topics:
            counts[t] += 1
    return [t for t, _ in counts.most_common(10)]


def detect_patterns(
    sessions: list[SessionEntry],
) -> list[str]:
    """Generate human-readable pattern observations."""
    if not sessions:
        return []
    patterns: list[str] = []
    _detect_provider_dominance(sessions, patterns)
    _detect_session_stats(sessions, patterns)
    _detect_project_focus(sessions, patterns)
    return patterns


def _detect_provider_dominance(
    sessions: list[SessionEntry],
    patterns: list[str],
) -> None:
    """Check if one provider dominates usage."""
    counts = Counter(s.provider for s in sessions)
    total = len(sessions)
    for prov, count in counts.most_common(1):
        pct = count * 100 // total
        if pct >= 70:
            patterns.append(
                f"{pct}% of sessions use {prov}"
            )


def _detect_session_stats(
    sessions: list[SessionEntry],
    patterns: list[str],
) -> None:
    """Compute average session statistics."""
    avg_prompts = (
        sum(s.prompt_count for s in sessions)
        // len(sessions)
    )
    durations = [
        s.duration_minutes for s in sessions
        if s.duration_minutes is not None
    ]
    if durations:
        avg_min = sum(durations) / len(durations)
        patterns.append(
            f"Average session: {avg_prompts} prompts, "
            f"{avg_min:.0f} minutes"
        )
    else:
        patterns.append(
            f"Average session: {avg_prompts} prompts"
        )


def _detect_project_focus(
    sessions: list[SessionEntry],
    patterns: list[str],
) -> None:
    """Detect high-activity projects."""
    by_proj = Counter(s.project for s in sessions)
    for proj, count in by_proj.most_common(1):
        if count >= 5:
            patterns.append(
                f"Project '{proj}' had {count} sessions"
                f" — high focus"
            )


def _merge_topics(
    sessions: list[SessionEntry],
) -> list[str]:
    """Merge topics across sessions by frequency."""
    counts: Counter[str] = Counter()
    for s in sessions:
        for t in s.topics:
            counts[t] += 1
    return [t for t, _ in counts.most_common(10)]
