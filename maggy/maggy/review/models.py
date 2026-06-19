"""Typed review schema. A `Finding` maps 1:1 to a GitHub inline review comment."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Severity(str, Enum):
    blocking = "blocking"   # must fix before merge
    nit = "nit"             # non-blocking suggestion


class Finding(BaseModel):
    file: str = Field(description="repo-relative path the finding is about")
    line: int | None = Field(
        default=None,
        description="1-based line in the file's NEW version to attach the comment to; null = file-level",
    )
    severity: Severity
    title: str = Field(description="one-line summary of the issue")
    detail: str = Field(description="explanation and why it matters")
    suggestion: str | None = Field(default=None, description="concrete fix, if any")
    evidence: str | None = Field(
        default=None,
        description="what tool call / file:line proves this — REQUIRED for a blocking finding so we don't post guesses",
    )


class Verdict(BaseModel):
    decision: Literal["approve", "changes_needed"]
    summary: str = Field(description="2-4 sentence overall summary for the PR author")
    findings: list[Finding] = Field(default_factory=list)


class Refutation(BaseModel):
    """A skeptic's verdict on whether a blocking finding holds up."""
    refuted: bool = Field(description="true ONLY if you found concrete evidence the finding is FALSE")
    reason: str = Field(description="why it's refuted (or why it stands)")
    evidence: str | None = Field(default=None, description="the grep/read result that disproves the claim")


class BlastRadius(BaseModel):
    """Computed during planning — drives how big a council we summon."""
    impacted_files: list[str] = Field(default_factory=list)
    impacted_symbols: list[str] = Field(default_factory=list)
    impacted_endpoints: list[str] = Field(default_factory=list)
    cross_service: bool = Field(default=False, description="does the change cross a service/bounded-context boundary?")
    touches_auth_or_data: bool = Field(default=False, description="auth, migrations, money, or PII paths involved?")
    languages: list[str] = Field(default_factory=list, description="subset of {db, python, typescript}")
    size: Literal["small", "medium", "large"] = "small"
    rationale: str = ""


class ReviewChunk(BaseModel):
    name: str
    focus: str = Field(description="what to scrutinize in this area")
    files: list[str]
    languages: list[str] = Field(default_factory=list)


class ReviewPlan(BaseModel):
    """The planner's output: blast radius + a council sized to it."""
    blast_radius: BlastRadius
    council_size: int = Field(
        ge=1, le=6,
        description="how many reviewer agents to summon, sized to blast radius (small=2, medium=4, large/auth=6)",
    )
    rounds: Literal[1, 2] = Field(default=1, description="1 = independent only; 2 = + a discussion round")
    chunks: list[ReviewChunk] = Field(
        default_factory=list,
        description="review areas for a large PR (one panel per chunk); empty = single-pass review",
    )
    reason: str = Field(default="", description="why this council size/shape fits the blast radius")
