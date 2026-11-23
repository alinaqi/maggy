"""Required checks run by the runner in a fresh worktree at the candidate (RFC §2.6.2/7)."""

from __future__ import annotations

import json
import pwd
import os
import sys
from pathlib import Path

import pytest

from maggy.harness.schema import HarnessProfile
from maggy.worker.checks import CheckPlan, required_commands, run_checks
from maggy.worker.models import WorkerSpec
from maggy.worker.pipeline import Attempt, run_attempt
from maggy.worker.worktree import create_attempt_worktree
from worker_git_helpers import (DUMP_CHECK, FAKE_AGENT, dump_command, fake_adapter, git,
                                init_repo, profile, write_script)

REAL_HOME = pwd.getpwuid(os.getuid()).pw_dir


@pytest.fixture
def secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("GITHUB_TOKEN", "AWG_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.setenv(name, "sekrit-value")


def _attempt(tmp_path: Path, exit_code: int = 0) -> tuple[Attempt, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    spec = WorkerSpec(awg_ref="AWG-9", attempt_id="att-2", fencing_token="local", stage="build",
                      repo=repo, base_commit=init_repo(repo), spec_version=0,
                      workspace=tmp_path / "wt", permission="workspace", deadline_s=30,
                      budget_usd=0.5, prompt="edit")
    create_attempt_worktree(spec)
    out = tmp_path / "dump.json"
    command = dump_command(write_script(tmp_path, "dump", DUMP_CHECK), out, exit_code)
    prof = profile(commands={"test": command}, required=["test"])
    agent = fake_adapter(write_script(tmp_path, "agent", FAKE_AGENT))
    return Attempt(spec=spec, adapter=agent, profile=prof, state_dir=tmp_path / "state"), out


def test_checks_run_on_fresh_worktree_at_candidate(tmp_path: Path, secrets: None) -> None:
    attempt, out = _attempt(tmp_path)
    result = run_attempt(attempt)
    dump = json.loads(out.read_text())
    assert Path(dump["cwd"]).resolve() != attempt.spec.workspace.resolve()
    assert dump["head"] == result.candidate_commit
    [check] = result.checks
    assert (check.name, check.passed, check.exit_code) == ("test", True, 0)
    assert check.sha == result.candidate_commit


def test_check_env_has_no_credentials(tmp_path: Path, secrets: None) -> None:
    attempt, out = _attempt(tmp_path)
    run_attempt(attempt)
    env = json.loads(out.read_text())["env"]
    assert "sekrit-value" not in env.values()
    assert not [k for k in env if k.startswith(("GITHUB_", "AWG_")) or k.endswith("API_KEY")]
    assert env["HOME"] not in (REAL_HOME, os.environ["HOME"])


def test_failing_check_is_recorded_as_failed(tmp_path: Path) -> None:
    attempt, _ = _attempt(tmp_path, exit_code=3)
    [check] = run_attempt(attempt).checks
    assert (check.passed, check.exit_code) == (False, 3)
    assert check.log_path is not None and check.log_path.exists()


def test_fresh_check_worktree_is_removed(tmp_path: Path) -> None:
    attempt, _ = _attempt(tmp_path)
    run_attempt(attempt)
    listed = git(attempt.spec.repo, "worktree", "list", "--porcelain")
    assert listed.count("worktree ") == 2  # main checkout + the agent's attempt worktree


def test_missing_command_and_timeout_fail(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    sha = init_repo(repo)
    sleeper = f"{sys.executable} -c 'import time; time.sleep(30)'"
    plan = CheckPlan(repo=repo, sha=sha, work_dir=tmp_path / "checks", timeout_s=0.5,
                     commands=[("lint", None), ("test", sleeper)], profile=profile())
    lint, test = run_checks(plan)
    assert (lint.passed, lint.exit_code, lint.command) == (False, None, "")
    assert (test.passed, test.exit_code) == (False, None)
    assert test.duration_s < 10


def test_required_commands_map_validation_to_commands() -> None:
    prof = HarnessProfile.model_validate({"commands": {"test": "pytest -q", "lint": "ruff ."},
                                          "validation": {"required": ["lint", "e2e"]}})
    assert required_commands(prof) == [("lint", "ruff ."), ("e2e", None)]


def test_check_timeout_is_a_profile_setting() -> None:
    assert HarnessProfile().validation.check_timeout_s == 600
    prof = HarnessProfile.model_validate({"validation": {"check_timeout_s": 42}})
    assert prof.validation.check_timeout_s == 42
