"""Verify stage, visual side: baseline approval round trip and the vision reviewer gate
(RFC §2.5, §2.6.9; factory doc §5). Browser tests skip where chromium cannot run."""

from __future__ import annotations

from pathlib import Path

import pytest

from verify_helpers import GOOD_PAGE, FakeVision, browser, visual_entry
from verify_stage_helpers import verify_record, approve_baselines, make_verify_rig
from worker_git_helpers import git

__all__ = ["browser"]
BASELINES = [".maggy/baselines/AC3-desktop.png", ".maggy/baselines/AC3-mobile.png"]


def _rig(tmp_path: Path, vision: list) -> object:
    return make_verify_rig(tmp_path, ([visual_entry()], {"checkout.html": GOOD_PAGE}),
                           vision=vision)


@pytest.mark.usefixtures("browser")
def test_missing_baseline_waits_for_a_human_with_the_proposed_image(tmp_path: Path) -> None:
    rig = _rig(tmp_path, [FakeVision("pass")])
    report = rig.runner.run_once()
    item = rig.awg.items[rig.ref]
    assert report.outcome == "waiting_human" and item.state == "WAITING_HUMAN"
    question = item.comments[-1]["body"]
    assert "baseline-approved:AC3:mobile" in question and "baseline-approved:AC3:desktop" in question
    proposals = [a["data"] for a in item.annotations if a["key"].startswith("baseline-proposed:")]
    assert len(proposals) == 2 and all(Path(p["path"]).is_file() for p in proposals)
    assert all(p["path"] in question for p in proposals)
    assert all(Path(p["path"]).is_relative_to(rig.state / "attempts") for p in proposals)
    assert item.revision_sha is None


@pytest.mark.usefixtures("browser")
def test_approved_baseline_is_committed_and_the_check_passes(tmp_path: Path) -> None:
    vision = FakeVision("pass")
    rig = _rig(tmp_path, [vision])
    rig.runner.run_once()
    approve_baselines(rig)
    report = rig.runner.run_once()
    head = git(rig.repo, "rev-parse", f"maggy/{rig.ref}")
    assert report.outcome == "submitted" and report.detail == head
    assert sorted(git(rig.repo, "ls-tree", "-r", "--name-only", head, ".maggy").split()) \
        == BASELINES
    assert git(rig.repo, "log", "-1", "--format=%an", head) == "Maggy"
    visual = [e for e in rig.awg.items[rig.ref].evidence if e["meta"]["check"] == "visual"]
    assert {e["verdict"] for e in visual} == {"PASS"} and len(visual) == 2
    assert {e["commit_sha"] for e in visual} == {head}
    assert sorted(c.viewport for c in vision.calls) == ["desktop", "mobile"]
    assert vision.calls[0].criterion_text == "message sits under the coupon field"


@pytest.mark.usefixtures("browser")
def test_tampered_proposal_is_not_committed(tmp_path: Path) -> None:
    rig = _rig(tmp_path, [FakeVision("pass")])
    rig.runner.run_once()
    approve_baselines(rig)
    proposal = [a["data"] for a in rig.awg.items[rig.ref].annotations
                if a["key"].startswith("baseline-proposed:")][0]
    Path(proposal["path"]).write_bytes(b"not the approved image")
    rig.runner.run_once()
    head = git(rig.repo, "rev-parse", f"maggy/{rig.ref}")
    files = git(rig.repo, "ls-tree", "-r", "--name-only", head, ".maggy").split()
    assert f".maggy/baselines/AC3-{proposal['viewport']}.png" not in files


@pytest.mark.usefixtures("browser")
def test_no_vision_backend_keeps_the_gate_closed(tmp_path: Path) -> None:
    rig = _rig(tmp_path, [])
    rig.runner.run_once()
    approve_baselines(rig)
    report = rig.runner.run_once()
    assert report.outcome == "waiting_human" and "no vision backend" in report.detail
    assert rig.awg.items[rig.ref].revision_sha is None
    head = git(rig.repo, "rev-parse", f"maggy/{rig.ref}")
    record = verify_record(rig, head)
    assert record["verdicts"] == {"AC3": "PENDING"}


@pytest.mark.usefixtures("browser")
def test_vision_failure_fails_the_criterion(tmp_path: Path) -> None:
    rig = _rig(tmp_path, [FakeVision("fail")])
    rig.runner.run_once()
    approve_baselines(rig)
    report = rig.runner.run_once()
    assert report.outcome == "failed" and "[AC3] vision" in report.detail


@pytest.mark.usefixtures("browser")
def test_human_vision_review_at_the_candidate_opens_the_gate(tmp_path: Path) -> None:
    rig = _rig(tmp_path, [])
    rig.runner.run_once()
    approve_baselines(rig)
    question = rig.runner.run_once().detail
    head = git(rig.repo, "rev-parse", f"maggy/{rig.ref}")
    for viewport in ("mobile", "desktop"):
        key = f"vision-reviewed:AC3:{viewport}"
        assert key in question
        rig.awg.nodes.append({"id": f"N-{len(rig.awg.nodes) + 1}", "type": "DECISION",
                              "key": key, "data": {"sha": head}, "parent": rig.ref})
    rig.awg.items[rig.ref].state = "READY"
    assert rig.runner.run_once().outcome == "submitted"
