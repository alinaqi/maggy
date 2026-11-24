"""No review council wired in is verification PENDING, never a pass (RFC §2.5 PR row):
the gate waits for a human, who can record a `pr-reviewed` DECISION at the tested sha."""

from __future__ import annotations

from pathlib import Path

from maggy.runner.pr_evidence.council import ReviewRequest, run_council
from regression_helpers import CALC_FIXED, TEST_ADD
from verify_helpers import functional_entry
from verify_stage_helpers import make_verify_rig
from worker_git_helpers import git

FIX = {"calc.py": CALC_FIXED, "tests/test_calc.py": TEST_ADD}


def test_no_council_is_a_review_that_could_not_run() -> None:
    outcome = run_council(None, ReviewRequest("AWG-1", "1", "abc", (), (), ""))
    assert outcome.failed and "no review council configured" in outcome.gap


def test_no_council_waits_for_a_human_instead_of_submitting(tmp_path: Path) -> None:
    rig = make_verify_rig(tmp_path, ([functional_entry()], FIX), council=None)
    report = rig.runner.run_once()
    sha = git(rig.repo, "rev-parse", f"maggy/{rig.ref}")
    assert report.outcome == "waiting_human"
    assert "no review council configured" in report.detail
    assert f"--key pr-reviewed --data '{{\"sha\": \"{sha}\"}}'" in report.detail
    assert rig.awg.items[rig.ref].revision_sha is None
    body = next(rig.state.rglob("pr-evidence.md")).read_text()
    assert "Gate: closed (verification is pending" in body


def test_a_human_review_at_the_tested_sha_opens_the_gate(tmp_path: Path) -> None:
    rig = make_verify_rig(tmp_path, ([functional_entry()], FIX), council=None)
    assert rig.runner.run_once().outcome == "waiting_human"
    sha = git(rig.repo, "rev-parse", f"maggy/{rig.ref}")
    _record_review(rig, "0" * 40)
    assert rig.runner.run_once().outcome == "waiting_human", "a review of another sha"
    _record_review(rig, sha)
    report = rig.runner.run_once()
    assert report.outcome == "submitted"
    body = sorted(rig.state.rglob("pr-evidence.md"))[-1].read_text()
    assert "a human recorded the review" in body


def _record_review(rig, sha: str) -> None:
    """A human's `pr-reviewed` DECISION, then the item back to READY."""
    rig.awg.items[rig.ref].state = "READY"
    rig.awg.nodes.append({"id": f"N-{len(rig.awg.nodes) + 1}", "type": "DECISION",
                          "key": "pr-reviewed", "data": {"sha": sha}, "parent": rig.ref})
