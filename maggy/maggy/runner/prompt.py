"""The worker prompt from the AWG context bundle; ticket text stays delimited data (§2.6.6)."""

from __future__ import annotations

from maggy.runner.awg_types import Claim
from maggy.worker.blocker import BLOCKER_INSTRUCTIONS
from maggy.worker.prompt import assemble_prompt

TASK = ("You are implementing one work item in this repository, test first: write failing "
        "tests for each acceptance criterion, then the minimal code to pass them. Do not "
        "commit, push or open pull requests; the runner does that. " + BLOCKER_INSTRUCTIONS)


def build_prompt(claim: Claim) -> str:
    criteria = "\n".join(f"- {line}" for line in claim.acceptance_criteria) or "- (none)"
    ticket = (f"Title: {claim.title}\n\nDescription:\n{claim.description}\n\n"
              f"Acceptance criteria:\n{criteria}\n\nContext bundle:\n{claim.context}")
    return assemble_prompt(TASK, ticket)
