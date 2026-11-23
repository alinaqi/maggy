"""worker.isolation / worker.allow_host_execution: schema, personal-only, doctor warning."""

from __future__ import annotations

from pathlib import Path

import pytest
from harness_cli_helpers import TESTED, FakeTools, invoke, make_env, write_profile, write_tokens
from harness_helpers import repo_file, write_yaml
from pydantic import ValidationError

from maggy.harness import HarnessConfigError, resolve_profile
from maggy.harness.schema import HarnessProfile

AGENTS = ["claude", "codex", "opencode", "pi"]


def test_defaults_are_worktree_and_no_host_execution():
    worker = HarnessProfile().worker
    assert worker.isolation == "worktree" and worker.allow_host_execution is False


def test_unknown_isolation_rejected():
    with pytest.raises(ValidationError, match="isolation"):
        HarnessProfile.model_validate({"worker": {"isolation": "vm"}})


def test_personal_profile_may_allow_host_execution(tmp_path: Path):
    home = write_yaml(tmp_path / "home" / "harness.yaml", {"worker": {"allow_host_execution": True}})
    resolved = resolve_profile(repo_root=tmp_path / "repo", personal_path=home)
    assert resolved.profile.worker.allow_host_execution is True
    assert resolved.provenance["worker.allow_host_execution"] == "personal"


def test_repo_profile_cannot_allow_host_execution(tmp_path: Path):
    root = tmp_path / "repo"
    write_yaml(repo_file(root), {"worker": {"allow_host_execution": True}})
    home = write_yaml(tmp_path / "home" / "harness.yaml", "")
    with pytest.raises(HarnessConfigError) as info:
        resolve_profile(repo_root=root, personal_path=home)
    message = str(info.value)
    assert str(repo_file(root)) in message
    assert "worker.allow_host_execution: only allowed in the personal profile" in message


def _doctor(tmp_path: Path, worker: dict) -> str:
    env = make_env(tmp_path, FakeTools(dict(TESTED), awg={"initialised": True}))
    write_profile(env, {"agents": {"installed": AGENTS}, "surfaces": [], "worker": worker})
    write_tokens(env, AGENTS)
    result = invoke(env, ["doctor"])
    assert result.exit_code == 0, result.output
    return result.output


def test_doctor_warns_when_host_execution_allowed(tmp_path: Path):
    output = _doctor(tmp_path, {"allow_host_execution": True})
    assert "WARN worker.allow_host_execution is true" in output


def test_doctor_silent_about_host_execution_by_default(tmp_path: Path):
    assert "allow_host_execution" not in _doctor(tmp_path, {})
