"""Verify stage, functional side (RFC §2.5, §2.6.2): repo commands and per-criterion
functional checks run in a fresh worktree at the integrated candidate with the check env."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from regression_helpers import CALC_FIXED, TEST_ADD
from verify_helpers import functional_entry
from verify_stage_helpers import verify_record, make_verify_rig
from worker_git_helpers import git

FIX = {"calc.py": CALC_FIXED, "tests/test_calc.py": TEST_ADD}
LEAK = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


def _evidence(rig, check: str) -> list[dict]:
    return [e for e in rig.awg.items[rig.ref].evidence if e["meta"].get("check") == check]


def test_checks_run_in_a_fresh_worktree_at_the_integrated_candidate(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "gh-secret-value")
    monkeypatch.setenv("AWG_TOKEN", "awg-secret-value")
    rig = make_verify_rig(tmp_path, ([functional_entry()], FIX))
    report = rig.runner.run_once()
    candidate = git(rig.repo, "rev-parse", f"maggy/{rig.ref}")
    assert report.outcome == "submitted" and report.detail == candidate
    assert git(rig.repo, "show", f"{candidate}:calc.py") == CALC_FIXED.strip()  # child merged
    dumped = json.loads(rig.check_out.read_text())
    assert dumped["head"] == candidate and Path(dumped["cwd"]) != rig.repo
    assert "GITHUB_TOKEN" not in dumped["env"] and "AWG_TOKEN" not in dumped["env"]
    assert dumped["env"]["HOME"] != str(Path.home())
    assert rig.awg.items[rig.ref].revision_sha == candidate


def test_per_criterion_evidence_is_commit_bound_with_spec_version(tmp_path: Path) -> None:
    rig = make_verify_rig(tmp_path, ([functional_entry()], FIX))
    report = rig.runner.run_once()
    candidate = git(rig.repo, "rev-parse", f"maggy/{rig.ref}")
    [proof] = _evidence(rig, "functional")
    assert proof["verdict"] == "PASS" and proof["commit_sha"] == candidate
    assert proof["kind"] == "test" and proof["producer"] == "ci"
    assert proof["meta"] == {"spec_version": str(report.spec_version), "criterion_id": "AC1",
                             "check": "functional"}
    [command] = _evidence(rig, "test")
    assert command["verdict"] == "PASS" and command["commit_sha"] == candidate


def test_failing_functional_check_fails_the_verify_step(tmp_path: Path) -> None:
    rig = make_verify_rig(tmp_path, ([functional_entry()], {"tests/test_calc.py": TEST_ADD}))
    report = rig.runner.run_once()
    assert report.outcome == "failed" and "[AC1] functional: FAIL" in report.detail
    assert rig.awg.items[rig.ref].state == "READY"
    assert _evidence(rig, "functional")[0]["verdict"] == "FAIL"


def test_unfinished_build_child_is_not_verified(tmp_path: Path) -> None:
    rig = make_verify_rig(tmp_path, ([functional_entry()], FIX))
    rig.awg.items[rig.child].state = "ACTIVE"
    report = rig.runner.run_once()
    assert report.outcome == "waiting_children" and rig.child in report.detail
    assert not rig.check_out.exists()


def test_secret_scan_keeps_a_leaky_artifact_out_of_the_pr_record(
        tmp_path: Path) -> None:
    printer = {"tests/test_calc.py": TEST_ADD.replace(
        "assert add", f"print('token {LEAK}')\n    assert add"), "calc.py": CALC_FIXED}
    rig = make_verify_rig(tmp_path, ([functional_entry()], printer))
    rig.runner.config.profile.validation.regression.command += " -s"
    assert rig.runner.run_once().outcome == "submitted"
    candidate = git(rig.repo, "rev-parse", f"maggy/{rig.ref}")
    record = verify_record(rig, candidate)
    assert record is not None and record["withheld"]
    assert all("functional" in path for path in record["withheld"])
    referenced = " ".join(record["artifacts"])
    assert all(path not in referenced for path in record["withheld"])
    for path in record["artifacts"]:
        assert LEAK not in Path(path).read_text(errors="replace")
