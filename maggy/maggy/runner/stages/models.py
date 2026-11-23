"""Structured outputs of the spec stage workers (RFC §2.5)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Shape(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Criterion(Shape):
    id: str = Field(min_length=1, max_length=20)
    text: str = Field(min_length=1)
    kind: Literal["functional", "ui", "nonfunctional"]
    testable: bool


class SpecDraft(Shape):
    acceptance_criteria: list[Criterion] = Field(min_length=1)
    open_questions: list[str] = []
    assumptions: list[str] = []
    risk_paths: list[str] = []


class SpecReview(Shape):
    verdict: Literal["ready", "needs_clarification", "blocked"]
    question: str | None = None
    issues: list[str] = []

    @model_validator(mode="after")
    def _one_question(self) -> SpecReview:
        """needs_clarification carries exactly ONE precise question (never zero, never two)."""
        if self.verdict != "needs_clarification":
            return self
        question = (self.question or "").strip()
        if not question or question.count("?") > 1:
            raise ValueError("needs_clarification requires exactly one question")
        return self

    def reason(self) -> str:
        """Why the item waits for a human: the question, else the issues."""
        return self.question or "; ".join(self.issues) or "spec review blocked the item"
