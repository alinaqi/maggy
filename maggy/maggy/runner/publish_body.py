"""The draft PR's title and body: summary, AWG ref, candidate SHA and the checks table."""

from __future__ import annotations

from maggy.runner.awg_types import Claim
from maggy.worker.models import WorkerResult


def pr_title(claim: Claim) -> str:
    title = " ".join(claim.title.split())
    return f"maggy: {claim.ref} {title}".strip()[:200]


def render_body(claim: Claim, result: WorkerResult, evidence: str = "") -> str:
    """`evidence`: the verify stage's per-criterion evidence record (markdown), if any."""
    sha = result.candidate_commit or ""
    rows = [f"| {_cell(c.name)} | {'PASS' if c.passed else 'FAIL'} | `{c.sha}` |"
            for c in result.checks]
    return "\n".join([
        "## Summary", "", f"Candidate for {claim.ref} produced by the Maggy runner.", "",
        f"- AWG ref: `{claim.ref}`", f"- Candidate SHA: `{sha}`",
        f"- Attempt: `{claim.attempt_id}`", "",
        "## Checks", "", "| Check | Result | SHA |", "|---|---|---|", *rows, "",
        *([evidence.rstrip("\n"), ""] if evidence else []),
        "Draft opened by the Maggy runner; it never merges or marks a PR ready.", ""])


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")
