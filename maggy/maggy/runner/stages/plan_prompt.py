"""Plan-stage prompt: runner instructions first, the ticket and repo context as one delimited
block of untrusted data (RFC §2.6.6), reusing the spec stage's ticket data."""

from __future__ import annotations

from maggy.runner.stages.spec_prompt import READ_ONLY, REPLY, SpecContext, ticket_data
from maggy.worker.prompt import assemble_prompt

PLANNER = (READ_ONLY + "Plan the implementation of the work item described in the data below "
           "as small tasks: unique keys (T1, T2, ...), the repository-relative files each task "
           "changes, and depends_on naming other task keys (no cycles). Then a test plan with at "
           "least one entry per acceptance criterion id ([AC1] ...): the task that makes it pass, "
           "the fixture, the action, the expected result, the evidence (unit, integration, e2e, "
           "visual or manual) and the name of the regression test that proves it. A visual "
           "entry may add \"visual\": {\"route\": \"<file in the repo>\", \"viewports\": "
           "[{\"name\", \"width\", \"height\"}], \"actions\": [{\"do\", \"selector\", "
           "\"value\"}], \"assertions\": [{\"check\", \"selector\", \"other\", "
           "\"value\"}]} for a Maggy-run browser check. " + REPLY +
           '{"tasks": [{"key": "T1", "title": "...", "description": "...", "files": ["src/x.py"], '
           '"depends_on": []}], "test_plan": [{"criterion_id": "AC1", "task": "T1", '
           '"fixture": "...", "action": "...", "expected": "...", "evidence": "unit", '
           '"regression_test_name": "test_..."}]}')


def plan_prompt(ctx: SpecContext, risk_paths: list[str]) -> str:
    flagged = "\n".join(f"- {path}" for path in risk_paths) or "(none)"
    return assemble_prompt(PLANNER, ticket_data(ctx, f"Risky paths flagged by the spec:\n{flagged}"))
