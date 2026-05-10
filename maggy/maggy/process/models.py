"""Dataclasses for Process Intelligence — PR records, reviews, CI checks."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ReviewRecord:
    """A single PR review event."""

    reviewer: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED
    body: str
    submitted_at: str


@dataclass
class CheckRecord:
    """A single CI check run result."""

    name: str
    conclusion: str  # success, failure, neutral, skipped
    started_at: str
    completed_at: str


@dataclass
class PRRecord:
    """A pull request with computed metrics."""

    number: int
    title: str
    author: str
    state: str  # open, closed, merged
    created_at: str
    merged_at: str | None
    additions: int
    deletions: int
    changed_files: int
    head_sha: str
    base_branch: str
    reviews: list[ReviewRecord] = field(default_factory=list)
    checks: list[CheckRecord] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    @property
    def total_lines(self) -> int:
        return self.additions + self.deletions

    @property
    def review_rounds(self) -> int:
        return sum(
            1 for r in self.reviews
            if r.state == "CHANGES_REQUESTED"
        )

    @property
    def time_to_merge_hours(self) -> float | None:
        if not self.merged_at or not self.created_at:
            return None
        from datetime import datetime, timezone
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        try:
            created = datetime.strptime(self.created_at, fmt)
            merged = datetime.strptime(self.merged_at, fmt)
            created = created.replace(tzinfo=timezone.utc)
            merged = merged.replace(tzinfo=timezone.utc)
            return (merged - created).total_seconds() / 3600
        except (ValueError, TypeError):
            return None

    @property
    def ci_passed(self) -> bool:
        if not self.checks:
            return True
        return all(
            c.conclusion in ("success", "neutral", "skipped")
            for c in self.checks
        )


@dataclass
class ReviewSignal:
    """Recurring theme from a reviewer."""

    reviewer: str
    theme: str
    count: int
    example_prs: list[int] = field(default_factory=list)


@dataclass
class CISignal:
    """CI failure pattern."""

    check_name: str
    failure_count: int
    total_runs: int
    correlated_files: list[str] = field(default_factory=list)

    @property
    def failure_rate(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.failure_count / self.total_runs


@dataclass
class VelocitySignal:
    """PR velocity metrics."""

    avg_time_to_merge_hours: float
    median_time_to_merge_hours: float
    avg_review_rounds: float
    avg_pr_size: float
    total_prs_analyzed: int


@dataclass
class ProcessReport:
    """The 5-minute analysis report."""

    project_key: str
    generated_at: str
    total_prs: int
    velocity: VelocitySignal | None = None
    review_signals: list[ReviewSignal] = field(default_factory=list)
    ci_signals: list[CISignal] = field(default_factory=list)
    routing_recommendations: list[dict] = field(
        default_factory=list
    )
    preemptive_fixes: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class ModelTier:
    """A model tier for dynamic routing."""

    name: str
    provider: str
    model: str
    cost_rank: int  # 1=cheapest, 5=most expensive
    complexity_min: int  # Min complexity score
    complexity_max: int  # Max complexity score
    strengths: list[str] = field(default_factory=list)
    role: str = "primary"  # "primary" | "validator"
