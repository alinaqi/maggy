"""Plan and PlanDiff models for dual-model planning."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PlanStep:
    """A single step in a plan."""

    description: str
    files: list[str] = field(default_factory=list)
    blast_estimate: int = 0


@dataclass
class Plan:
    """A generated implementation plan."""

    task: str
    model: str
    steps: list[PlanStep] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    total_blast: int = 0

    @property
    def step_count(self) -> int:
        return len(self.steps)


@dataclass
class PlanDiff:
    """Diff between primary and counter plans."""

    agreed: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    primary_only: list[str] = field(default_factory=list)
    counter_only: list[str] = field(default_factory=list)

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def agreement_ratio(self) -> float:
        total = (
            len(self.agreed) + len(self.conflicts)
            + len(self.primary_only) + len(self.counter_only)
        )
        if total == 0:
            return 1.0
        return len(self.agreed) / total
