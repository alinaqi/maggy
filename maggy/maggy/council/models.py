"""Council dataclasses — context, votes, analysis, decisions."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContextPackage:
    goal: str
    plan_text: str
    code_diff: str = ""
    issue_context: str = ""
    affected_code: list[str] = field(default_factory=list)
    prior_decisions: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [self.goal[:120], self.plan_text[:120]]
        return " | ".join(p for p in parts if p)[:300]


@dataclass
class ReviewerVote:
    reviewer_id: str
    round_num: int
    verdict: str
    reasoning: str = ""
    concerns: list[str] = field(default_factory=list)

    @property
    def is_approve(self) -> bool:
        return self.verdict == "APPROVE"

    def to_dict(self) -> dict:
        return {
            "reviewer_id": self.reviewer_id,
            "round": self.round_num,
            "verdict": self.verdict,
            "reasoning": self.reasoning,
            "concerns": self.concerns,
        }


@dataclass
class DeliberationResult:
    final_votes: list[ReviewerVote]
    rounds_needed: int
    threshold: int
    discussion_log: list[dict] = field(default_factory=list)

    @property
    def approve_count(self) -> int:
        return sum(1 for v in self.final_votes if v.is_approve)

    @property
    def approved(self) -> bool:
        return self.approve_count >= self.threshold

    @property
    def consensus(self) -> bool:
        if not self.final_votes:
            return False
        first = self.final_votes[0].verdict
        return all(v.verdict == first for v in self.final_votes)


@dataclass
class BlastAnalysis:
    files_changed: int
    functions_affected: int
    subsystems_crossed: int
    test_coverage: float
    has_public_api_changes: bool = False
    has_auth_changes: bool = False
    has_ui_changes: bool = False

    @property
    def severity(self) -> str:
        if self.has_auth_changes or self.has_public_api_changes:
            return "critical"
        if self.files_changed >= 10 or self.subsystems_crossed >= 3:
            return "high"
        if self.files_changed >= 4 or self.subsystems_crossed >= 2:
            return "medium"
        return "low"


@dataclass
class ValidationClassification:
    objective_checks: list[str] = field(default_factory=list)
    subjective_reasons: list[str] = field(default_factory=list)

    @property
    def validation_type(self) -> str:
        has_obj = len(self.objective_checks) > 0
        has_subj = len(self.subjective_reasons) > 0
        if has_obj and has_subj:
            return "HYBRID"
        if has_subj:
            return "SUBJECTIVE"
        return "OBJECTIVE"

    @property
    def auto_executable(self) -> bool:
        return self.validation_type == "OBJECTIVE"


@dataclass
class ExecutionDecision:
    action: str
    reason: str
    rollback_point: str | None = None
    validation_steps: list[str] = field(default_factory=list)
