"""Data models for session history analysis."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class SessionEntry:
    """A single parsed session from any CLI."""

    session_id: str
    provider: str  # "claude" | "codex" | "kimi"
    project: str
    started_at: str
    ended_at: str
    prompt_count: int
    tool_use_count: int
    models_used: list[str] = field(default_factory=list)
    git_branch: str = ""
    topics: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def duration_minutes(self) -> float | None:
        """Session duration in minutes."""
        if not self.started_at or not self.ended_at:
            return None
        try:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.ended_at)
            return (end - start).total_seconds() / 60
        except (ValueError, TypeError):
            return None


@dataclass
class ProjectActivity:
    """Aggregated activity for a project across CLIs."""

    project: str
    total_sessions: int
    total_prompts: int
    providers_used: list[str] = field(default_factory=list)
    date_range: tuple[str, str] = ("", "")
    top_topics: list[str] = field(default_factory=list)


@dataclass
class ProviderUsage:
    """Usage statistics per provider."""

    provider: str
    session_count: int
    prompt_count: int
    total_minutes: float
    models_used: list[str] = field(default_factory=list)


@dataclass
class TimeDistribution:
    """Work distribution across time periods."""

    by_hour: dict[int, int] = field(default_factory=dict)
    by_weekday: dict[int, int] = field(default_factory=dict)
    by_date: dict[str, int] = field(default_factory=dict)


@dataclass
class HistoryReport:
    """Complete analysis report."""

    generated_at: str
    total_sessions: int
    total_prompts: int
    providers: list[ProviderUsage] = field(
        default_factory=list
    )
    projects: list[ProjectActivity] = field(
        default_factory=list
    )
    time_distribution: TimeDistribution | None = None
    top_topics: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    summary: str = ""


def _now_iso() -> str:
    """Current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()
