"""The build conclude proves each planned regression test before publishing (RFC §2.5)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from regression_helpers import (CALC_BUGGY, PYTEST, TEST_ADD, TEST_ZERO, commit_all,
                                plan_entry, write_files)
from runner_loop_helpers import Rig, make_rig
from worker_git_helpers import git, profile_data

FIX_AGENT = """
from pathlib import Path
Path("calc.py").write_text("def add(a, b):\\n    return a + b\\n")
Path("tests").mkdir(exist_ok=True)
Path("tests/test_calc.py").write_text({test!r})
"""


def _rig(tmp_path: Path, test_body: str) -> Rig:
    rig = make_rig(tmp_path, FIX_AGENT.format(test=test_body))
    write_files(rig.repo, {"calc.py": CALC_BUGGY})
    commit_all(rig.repo, "calc")
    data = profile_data({"test": rig.runner.config.profile.commands.test}, ["test"])
    data["validation"]["regression"] = {"runner": "pytest", "command": PYTEST}
    rig.runner.config = replace(rig.runner.config,
                                profile=HarnessProfile.model_validate(data))
    item = rig.awg.items[rig.ref]
    item.annotations.append({"key": "task-plan", "data": {
        "key": "T1", "test_plan": [plan_entry("AC1", "test_add")]}})
    item.validations = [{"id": "V-1", "kind": "test", "required": True,
                         "title": "[AC1] test_add: sum"}]
    return rig


def test_proven_regression_is_attached_per_criterion_and_submitted(tmp_path: Path) -> None:
    rig = _rig(tmp_path, TEST_ADD)
    report = rig.runner.run_once()
    item = rig.awg.items[rig.ref]
    assert report.outcome == "submitted"
    [proof] = [e for e in item.evidence if e["meta"].get("check") == "regression"]
    base = git(rig.repo, "rev-parse", "HEAD")
    assert proof["commit_sha"] == item.revision_sha and proof["verdict"] == "PASS"
    assert proof["kind"] == "test" and proof["validation"] == "V-1"
    assert proof["meta"] == {"spec_version": str(report.spec_version), "criterion_id": "AC1",
                             "check": "regression", "base_commit": base,
                             "regression_test": "test_add", "result_kind": "proven"}


def test_not_red_fails_back_to_build_with_the_trace(tmp_path: Path) -> None:
    rig = _rig(tmp_path, TEST_ZERO)
    report = rig.runner.run_once()
    item = rig.awg.items[rig.ref]
    assert report.outcome == "failed" and item.state != "VERIFYING"
    [proof] = [e for e in item.evidence if e["meta"].get("check") == "regression"]
    assert proof["verdict"] == "FAIL" and proof["meta"]["result_kind"] == "not_red"
    handoff = item.comments[-1]["body"]
    assert handoff.startswith("[handoff ") and "] failed: " in handoff
    assert "[AC1] test_add: not_red" in handoff and "passes on base" in handoff
