"""The review council fed the approved spec (RFC §2.5 PR row), run in the trusted runner.

`maggy.review.pipeline.run_review` is not cleanly reusable here: it fetches the PR and its
files from the GitHub API with a GITHUB_TOKEN, takes no spec or criteria, and posts its own
review. So the runner talks to a `ReviewCouncil` (request in, `review.models.Verdict` out);
adapting the legacy pipeline to it (local diff, spec-aware prompts, no posting) is Phase 6.
A review that could not run (no council configured, or the council failed) is verification
PENDING, never a pass: the gate waits for a human, who may record a `pr-reviewed` DECISION
at the tested sha after reviewing the PR. Blocking findings send the candidate back to build.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from maggy.review.models import Finding, Severity, Verdict
from maggy.worker.git_ops import GitError, run_git

MAX_DIFF = 400_000
NOT_CONFIGURED = ("no review council configured: the review waits for a human (the review/ "
                  "pipeline is GitHub-bound; a spec-aware adapter is Phase 6)")
COUNCIL_GAPS = ("review council failed", "no review council configured")
PR_REVIEWED = "pr-reviewed"  # a human's review of the PR: DECISION data {"sha": <tested sha>}


@dataclass(frozen=True)
class ReviewRequest:
    ref: str
    spec_version: str
    sha: str
    criteria: tuple[str, ...]  # the approved acceptance criteria
    test_plan: tuple[dict, ...]  # the plan's per-criterion entries
    diff: str  # base...candidate


class ReviewCouncil(Protocol):
    def review(self, request: ReviewRequest) -> Verdict: ...


@dataclass(frozen=True)
class CouncilOutcome:
    blocking: tuple[Finding, ...] = ()
    gap: str = ""
    failed: bool = False  # the review could not run: the gate waits for a human


def run_council(council: ReviewCouncil | None, request: ReviewRequest) -> CouncilOutcome:
    if council is None:
        return CouncilOutcome(gap=NOT_CONFIGURED, failed=True)
    try:
        verdict = council.review(request)
    except Exception as exc:  # noqa: BLE001 - any council failure keeps the gate closed
        return CouncilOutcome(gap=f"review council failed: {type(exc).__name__}: {exc}"[:300],
                              failed=True)
    return CouncilOutcome(tuple(f for f in verdict.findings if f.severity == Severity.blocking))


def candidate_diff(repo: Path, base: str, sha: str) -> str:
    """`git diff base...sha` (argv only), or "" when the base is unknown here."""
    try:
        return run_git(repo, ["diff", f"{base}...{sha}"])[:MAX_DIFF]
    except GitError:
        return ""
