"""The worker prompt from the AWG context bundle; ticket text stays delimited data (§2.6.6).

A task the plan stage made carries a `task-plan` annotation (description, files, test plan);
its entries and regression test names go into the prompt (RFC §2.5 build stage)."""

from __future__ import annotations

from maggy.runner.awg_types import Claim
from maggy.worker.blocker import BLOCKER_INSTRUCTIONS
from maggy.worker.prompt import assemble_prompt

TASK = ("You are implementing one work item in this repository, test first: write failing "
        "tests for each acceptance criterion, then the minimal code to pass them. When the "
        "item has a test plan, write each named regression test first; it must fail before "
        "your change and pass after it. Do not commit, push or open pull requests; the runner "
        "does that. " + BLOCKER_INSTRUCTIONS)
ENTRY = ("- [{criterion_id}] regression test {regression_test_name}: fixture: {fixture}; "
         "action: {action}; expected: {expected}; evidence: {evidence}")


def build_prompt(claim: Claim, handoff: str = "", plan: dict | None = None) -> str:
    criteria = "\n".join(f"- {line}" for line in claim.acceptance_criteria) or "- (none)"
    ticket = (f"Title: {claim.title}\n\nDescription:\n{claim.description}\n\n"
              f"Acceptance criteria:\n{criteria}\n\nContext bundle:\n{claim.context}")
    ticket += plan_section(plan or {})
    if handoff:
        ticket += ("\n\nPrevious attempt handoff (the worktree resumes from its branch):\n"
                   f"{handoff}")
    return assemble_prompt(TASK, ticket)


def task_plan_of(annotations: list[dict]) -> dict:
    """The item's `task-plan` annotation data, or {} for items the plan stage did not make."""
    found = [a.get("data") or {} for a in annotations if a.get("key") == "task-plan"]
    return dict(found[0]) if found else {}


def plan_section(plan: dict) -> str:
    if not plan:
        return ""
    entries = "\n".join(ENTRY.format_map({**dict.fromkeys(ENTRY_KEYS, ""), **e})
                        for e in plan.get("test_plan") or []) or "- (none)"
    files = ", ".join(plan.get("files") or []) or "(none)"
    return (f"\n\nPlanned task {plan.get('key', '')}:\n{plan.get('description', '')}\n"
            f"Files: {files}\n\nTest plan for this task:\n{entries}")


ENTRY_KEYS = ("criterion_id", "regression_test_name", "fixture", "action", "expected", "evidence")
