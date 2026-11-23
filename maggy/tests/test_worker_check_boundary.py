"""Required checks run candidate code: they need a boundary too (RFC §2.6.7).

No check sandbox exists yet (container isolation is Phase 4), so checks run on the host
only with the personal `worker.allow_host_execution: true`; otherwise the runner refuses
before launching the worker, even for natively sandboxed agents.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from maggy.harness.schema import HarnessProfile
from maggy.worker.checks import CheckPlan, run_checks
from maggy.worker.launch import Refused
from maggy.worker.models import WorkerSpec
from maggy.worker.pipeline import Attempt, run_attempt
from maggy.worker.worktree import create_attempt_worktree
from worker_git_helpers import (FAKE_AGENT, fake_adapter_data, git, init_repo, profile_data,
                                write_script)
from maggy.worker.adapter_spec import AdapterSpec


def _attempt(tmp_path: Path, required: list[str], host: bool) -> Attempt:
    repo = tmp_path / "repo"
    repo.mkdir()
    spec = WorkerSpec(awg_ref="AWG-3", attempt_id="att-3", fencing_token="local", stage="build",
                      repo=repo, base_commit=init_repo(repo), spec_version=0,
                      workspace=tmp_path / "wt", permission="workspace", deadline_s=30,
                      budget_usd=0.5, prompt="edit")
    create_attempt_worktree(spec)
    data = fake_adapter_data(write_script(tmp_path, "agent", FAKE_AGENT))
    adapter = AdapterSpec.model_validate({**data, "sandbox": {"native": True}})
    prof = profile_data(commands={"test": "true"}, required=required)
    prof["worker"] = {"allow_host_execution": host}
    return Attempt(spec=spec, adapter=adapter, profile=HarnessProfile.model_validate(prof),
                   state_dir=tmp_path / "state")


def test_native_agent_with_required_checks_refused_without_host_opt_in(tmp_path: Path):
    attempt = _attempt(tmp_path, ["test"], host=False)
    with pytest.raises(Refused, match="checks") as info:
        run_attempt(attempt)
    assert "allow_host_execution" in str(info.value)
    assert not (attempt.spec.workspace / "new_file.txt").exists(), "worker launched"


def test_native_agent_without_required_checks_still_runs(tmp_path: Path):
    attempt = _attempt(tmp_path, [], host=False)
    result = run_attempt(attempt)
    assert result.candidate_commit is not None and result.checks == []


def test_checks_run_with_host_opt_in(tmp_path: Path):
    [check] = run_attempt(_attempt(tmp_path, ["test"], host=True)).checks
    assert check.passed is True


def test_run_checks_refuses_host_execution_by_default(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    sha = init_repo(repo)
    plan = CheckPlan(repo=repo, sha=sha, work_dir=tmp_path / "checks", commands=[("t", "true")])
    with pytest.raises(Refused, match="allow_host_execution"):
        run_checks(plan)
    assert git(repo, "worktree", "list", "--porcelain").count("worktree ") == 1
