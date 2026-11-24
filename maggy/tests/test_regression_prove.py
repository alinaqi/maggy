"""RED at base (+ candidate tests only), GREEN at candidate, both in fresh worktrees."""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.runner.regression.prove import ProofPlan, prove
from maggy.worker.launch import Refused
from regression_helpers import (CALC_FIXED, PYTEST, TEST_ADD, TEST_FIXTURE, TEST_IMPORT,
                                TEST_ZERO, fixture_repo, plan_entry, regression_profile)
from worker_git_helpers import git, profile


def _prove(tmp_path: Path, candidate: dict[str, str], test: str = "test_add"):
    repo, base, sha = fixture_repo(tmp_path, candidate)
    plan = ProofPlan(repo=repo, commits=(base, sha), work_dir=tmp_path / "proof",
                     profile=regression_profile())
    return prove(plan, plan_entry("AC1", test)), repo


def test_proven_fails_on_base_with_an_assertion_and_passes_on_candidate(tmp_path: Path) -> None:
    proof, repo = _prove(tmp_path, {"calc.py": CALC_FIXED, "tests/test_calc.py": TEST_ADD})
    assert (proof.outcome, proof.red, proof.green) == ("proven", "assertion", "passed")
    assert (proof.criterion_id, proof.test) == ("AC1", "test_add")
    listed = git(repo, "worktree", "list", "--porcelain")
    assert listed.count("worktree ") == 1, "both fresh worktrees are removed"


def test_not_red_when_the_test_already_passes_on_base(tmp_path: Path) -> None:
    proof, _ = _prove(tmp_path, {"calc.py": CALC_FIXED, "tests/test_calc.py": TEST_ZERO})
    assert (proof.outcome, proof.red, proof.green) == ("not_red", "passed", None)
    assert "passes on base" in proof.trace


def test_import_error_is_a_setup_error_not_a_red(tmp_path: Path) -> None:
    fixed = CALC_FIXED + "\n\ndef mul(a, b):\n    return a * b\n"
    proof, _ = _prove(tmp_path, {"calc.py": fixed, "tests/test_calc.py": TEST_IMPORT})
    assert (proof.outcome, proof.red) == ("setup_error", "error")
    assert "mul" in proof.trace


def test_missing_fixture_is_a_setup_error(tmp_path: Path) -> None:
    proof, _ = _prove(tmp_path, {"calc.py": CALC_FIXED, "tests/test_calc.py": TEST_FIXTURE})
    assert (proof.outcome, proof.red) == ("setup_error", "error")
    assert "coupon_db" in proof.trace


def test_unknown_test_name_is_a_setup_error(tmp_path: Path) -> None:
    proof, _ = _prove(tmp_path, {"calc.py": CALC_FIXED, "tests/test_calc.py": TEST_ADD},
                      test="test_nonexistent")
    assert (proof.outcome, proof.red) == ("setup_error", "missing")


def test_not_green_when_the_candidate_does_not_fix_it(tmp_path: Path) -> None:
    proof, _ = _prove(tmp_path, {"tests/test_calc.py": TEST_ADD})
    assert (proof.outcome, proof.red, proof.green) == ("not_green", "assertion", "assertion")
    assert "assert" in proof.trace


def test_refused_without_host_execution_opt_in(tmp_path: Path) -> None:
    repo, base, sha = fixture_repo(tmp_path, {"tests/test_calc.py": TEST_ADD})
    closed = profile().model_copy(update={"worker": profile().worker.model_copy(
        update={"allow_host_execution": False})})
    plan = ProofPlan(repo=repo, commits=(base, sha), work_dir=tmp_path / "p", profile=closed)
    with pytest.raises(Refused):
        prove(plan, plan_entry())


def test_command_runner_reads_its_junit_from_the_checkout(tmp_path: Path) -> None:
    repo, base, sha = fixture_repo(tmp_path, {"calc.py": CALC_FIXED,
                                              "tests/test_calc.py": TEST_ADD})
    regression = {"runner": "command", "junit": "out/report.xml",
                  "command": f"{PYTEST} -k {{test}} -p no:cacheprovider "
                             "--junitxml=out/report.xml"}
    plan = ProofPlan(repo=repo, commits=(base, sha), work_dir=tmp_path / "p",
                     profile=regression_profile(regression))
    assert prove(plan, plan_entry()).outcome == "proven"


def test_a_broken_unrelated_test_file_does_not_mask_a_real_red(tmp_path: Path) -> None:
    """AC2's file cannot import on base; AC1's assertion-RED is still proven (bare name)."""
    other = "from calc import mul\n\n\ndef test_add_mul():\n    assert mul(2, 3) == 6\n"
    fixed = CALC_FIXED + "\n\ndef mul(a, b):\n    return a * b\n"
    proof, _ = _prove(tmp_path, {"calc.py": fixed, "tests/test_calc.py": TEST_ADD,
                                 "tests/test_other.py": other})
    assert (proof.outcome, proof.red, proof.green) == ("proven", "assertion", "passed")
