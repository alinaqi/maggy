"""Structured output of the plan stage worker (RFC §2.5): tasks + per-criterion test plan."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from maggy.runner.stages.models import Shape
from maggy.runner.stages.plan_check import plan_problems
from maggy.runner.stages.visual_models import VisualSpec

KEY = r"^[A-Za-z0-9_.-]{1,40}$"
AUTOMATED = ("unit", "integration", "e2e", "visual")


class PlanTask(Shape):
    key: str = Field(pattern=KEY)
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    files: list[str] = []
    depends_on: list[str] = []


class TestPlanEntry(Shape):
    __test__ = False  # not a pytest class

    criterion_id: str = Field(min_length=1, max_length=20)
    task: str = Field(pattern=KEY)
    fixture: str = Field(min_length=1)
    action: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    evidence: Literal["unit", "integration", "e2e", "visual", "manual"]
    regression_test_name: str = Field(min_length=1, max_length=200)
    visual: VisualSpec | None = None  # a Maggy-run visual check (evidence: visual)

    def validation(self) -> tuple[str, int]:
        """(kind, min trust): automated evidence needs CI (3), manual acceptance reviewer (2)."""
        return ("test", 3) if self.evidence in AUTOMATED else ("acceptance", 2)


class Plan(Shape):
    tasks: list[PlanTask] = Field(min_length=1)
    test_plan: list[TestPlanEntry] = Field(min_length=1)


def checked_plan(criteria: list[str], repo: Path) -> type[Plan]:
    """Plan plus the graph checks for these criterion ids and this repo (so a bad plan is
    rejected like malformed JSON: one retry with the problems, then the stage fails)."""

    class CheckedPlan(Plan):
        @model_validator(mode="after")
        def _graph(self) -> CheckedPlan:
            problems = plan_problems(self, criteria, repo)
            if problems:
                raise ValueError("; ".join(problems))
            return self

    return CheckedPlan
