"""Verify -> PR (RFC §2.5 PR row): the draft PR body carries the per-criterion evidence
record, the review council (run by the runner) gets the approved spec, criteria, test plan
and diff, and blocking findings keep the gate closed. Fake gh + local bare remote."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

import pytest

from maggy.review.models import Finding, Severity, Verdict
from maggy.runner.pr_evidence.council import ReviewRequest
from maggy.runner.publish import PublishConfig, Publisher
from regression_helpers import CALC_FIXED, TEST_ADD
from runner_publish_helpers import FakeGh
from verify_helpers import functional_entry
from verify_stage_helpers import make_verify_rig
from worker_git_helpers import git

FIX = {"calc.py": CALC_FIXED, "tests/test_calc.py": TEST_ADD}
BLOCKER = Finding(file="calc.py", line=2, severity=Severity.blocking,
                  title="overflow unchecked", detail="add() never checks bounds")


@dataclass
class FakeCouncil:
    findings: list[Finding] = field(default_factory=list)
    error: Exception | None = None
    requests: list[ReviewRequest] = field(default_factory=list)

    def review(self, request: ReviewRequest) -> Verdict:
        self.requests.append(request)
        if self.error:
            raise self.error
        return Verdict(decision="approve", summary="ok", findings=self.findings)


def _rig(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, council: FakeCouncil):
    rig = make_verify_rig(tmp_path, ([functional_entry()], FIX))
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(rig.repo, "remote", "add", "origin", str(remote))
    gh = FakeGh(tmp_path / "ghbin")
    monkeypatch.setenv("PATH", f"{gh.root}:{os.environ['PATH']}")
    step = Publisher(rig.awg, PublishConfig(repo=rig.repo, state_dir=rig.state, base="main"))
    rig.runner.config = replace(rig.runner.config, pr_step=step, council=council)
    return rig, gh


def test_pr_body_carries_the_evidence_record_and_the_gate_opens(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rig, gh = _rig(tmp_path, monkeypatch, FakeCouncil())
    report = rig.runner.run_once()
    candidate = git(rig.repo, "rev-parse", f"maggy/{rig.ref}")
    assert report.outcome == "submitted"
    [pr] = gh.prs()
    assert pr["isDraft"] and pr["head"] == f"maggy/{rig.ref}"
    assert f"Tested commit: `{candidate}`" in pr["body"]
    assert f"Spec version: `{report.spec_version}`" in pr["body"]
    assert "| AC1 | passed | functional | unit |" in pr["body"]


def test_review_council_receives_spec_criteria_test_plan_and_diff(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    council = FakeCouncil()
    rig, _ = _rig(tmp_path, monkeypatch, council)
    report = rig.runner.run_once()
    [request] = council.requests
    item = rig.awg.items[rig.ref]
    assert list(request.criteria) == item.acceptance_criteria
    assert request.spec_version == str(report.spec_version)
    assert [e["criterion_id"] for e in request.test_plan] == ["AC1"]
    assert request.sha == git(rig.repo, "rev-parse", f"maggy/{rig.ref}")
    assert "calc.py" in request.diff and "+" in request.diff


def test_blocking_review_finding_keeps_the_gate_closed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rig, gh = _rig(tmp_path, monkeypatch, FakeCouncil(findings=[BLOCKER]))
    report = rig.runner.run_once()
    assert report.outcome == "failed" and "overflow unchecked" in report.detail
    assert rig.awg.items[rig.ref].revision_sha is None
    assert "overflow unchecked" in gh.prs()[0]["body"]


def test_council_failure_waits_for_a_human(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rig, gh = _rig(tmp_path, monkeypatch, FakeCouncil(error=RuntimeError("provider down")))
    report = rig.runner.run_once()
    assert report.outcome == "waiting_human" and "review council failed" in report.detail
    assert rig.awg.items[rig.ref].state == "WAITING_HUMAN"
    assert "review council failed" in gh.prs()[0]["body"]
