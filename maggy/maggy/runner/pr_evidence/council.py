"""The review council fed the approved spec (RFC §2.5 PR row), run in the trusted runner.

`maggy.review.pipeline.run_review` is not cleanly reusable here: it fetches the PR and its
files from the GitHub API with a GITHUB_TOKEN, takes no spec or criteria, and posts its own
review. So the runner talks to a `ReviewCouncil` (request in, `review.models.Verdict` out);
adapting the legacy pipeline to it (local diff, spec-aware prompts, no posting) is Phase 6.
No council configured is a recorded verification gap; a council that fails keeps the gate
closed (a human decides); its blocking findings send the candidate back to build.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from maggy.review.models import Finding, Severity, Verdict
from maggy.worker.git_ops import GitError, run_git

MAX_DIFF = 400_000
NOT_CONFIGURED = ("no review council configured: the review/ pipeline is GitHub-bound "
                  "(legacy; spec-aware adapter is Phase 6)")


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
    failed: bool = False


def run_council(council: ReviewCouncil | None, request: ReviewRequest) -> CouncilOutcome:
    if council is None:
        return CouncilOutcome(gap=NOT_CONFIGURED)
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
