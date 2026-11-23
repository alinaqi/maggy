"""Runner loop: blockers and protected paths go to WAITING_HUMAN; spec drift goes back (§2.4)."""

from __future__ import annotations

from pathlib import Path

from maggy.runner.awg_fake import FakeAwg
from maggy.runner.awg_types import Claim
from runner_loop_helpers import EDIT_AGENT, PROTECTED_AGENT, QUESTION_AGENT, decisions, make_rig


def _no_pr(claim, result) -> None:
    raise AssertionError("the PR step must not run")


def test_blocker_goes_to_waiting_human_with_question(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, QUESTION_AGENT, pr_step=_no_pr)
    report = rig.runner.run_once()
    item = rig.awg.items[rig.ref]
    assert report.outcome == "waiting_human" and item.state == "WAITING_HUMAN"
    assert any("Postgres or Redis?" in c["body"] for c in item.comments)
    assert item.revision_sha is None and "blocked" in decisions(rig)


def test_protected_path_goes_to_waiting_human(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, PROTECTED_AGENT, pr_step=_no_pr)
    report = rig.runner.run_once()
    item = rig.awg.items[rig.ref]
    assert report.outcome == "waiting_human" and item.state == "WAITING_HUMAN"
    assert any("src/payments/charge.py" in c["body"] for c in item.comments)
    assert item.revision_sha is None


class DriftingAwg(FakeAwg):
    """Someone edits the acceptance criteria while the worker runs (spec version bump)."""

    def heartbeat(self, claim: Claim) -> Claim:
        item = self.items[claim.ref]
        if item.acceptance_criteria == ["feature.txt exists"]:
            item.acceptance_criteria, item.version = ["feature.txt says hi"], item.version + 1
        return super().heartbeat(claim)


def test_spec_version_change_returns_item_for_spec_review(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT, awg=DriftingAwg(lease_seconds=900), pr_step=_no_pr)
    report = rig.runner.run_once()
    item = rig.awg.items[rig.ref]
    assert report.outcome == "spec_review" and item.state == "READY"
    assert item.evidence == [] and item.revision_sha is None
    assert any("spec review" in c["body"] for c in item.comments)


def test_unknown_stage_item_is_released_as_not_supported(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT, capabilities=["maggy-runner", "project:demo"],
                   attributes={"stage": "verify"}, pr_step=_no_pr)
    report = rig.runner.run_once()
    item = rig.awg.items[rig.ref]
    assert report.outcome == "unsupported" and item.state == "READY"
    assert not (rig.state / "worktrees" / rig.ref).exists()
