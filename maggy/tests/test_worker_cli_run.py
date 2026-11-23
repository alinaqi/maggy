"""`maggy worker run`: full pipeline end to end with a fake agent CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from maggy.cli import app
from maggy.worker.models import WorkerResult
from worker_git_helpers import (DUMP_CHECK, FAKE_AGENT, dump_command, fake_adapter_data, git,
                                init_repo, profile_data, write_script)
from worker_helpers import write_adapter


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    (home / ".maggy").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    write_adapter(home / ".maggy" / "adapters",
                  fake_adapter_data(write_script(tmp_path, "agent", FAKE_AGENT)))
    return home


def _personal(home: Path, data: dict) -> None:
    (home / ".maggy" / "harness.yaml").write_text(yaml.safe_dump(data))


def _invoke(tmp_path: Path, prompt: str, *extra: str):
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    if not (repo / ".git").exists():
        init_repo(repo)
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(prompt)
    args = ["worker", "run", "--adapter", "fakeedit", "--repo", str(repo),
            "--prompt-file", str(prompt_file), *extra]
    return CliRunner().invoke(app, args), repo


def test_run_prints_worker_result_json(tmp_path: Path, home: Path) -> None:
    out = tmp_path / "dump.json"
    command = dump_command(write_script(tmp_path, "dump", DUMP_CHECK), out)
    _personal(home, profile_data({"test": command}, ["test"]))
    run, repo = _invoke(tmp_path, "edit", "--deadline", "60", "--budget", "0.2")
    assert run.exit_code == 0, run.output
    result = WorkerResult.model_validate_json(run.stdout)
    assert result.candidate_commit and result.agent == "fakeedit"
    assert git(repo, "cat-file", "-t", result.candidate_commit) == "commit"
    assert [c.passed for c in result.checks] == [True]
    assert result.outcome == "blocked"  # the fake agent edits .github/workflows


def test_run_without_changes_prints_null_candidate(tmp_path: Path, home: Path) -> None:
    _personal(home, profile_data())
    run, _ = _invoke(tmp_path, "noop", "--permission", "read_only")
    assert run.exit_code == 0, run.output
    result = WorkerResult.model_validate_json(run.stdout)
    assert result.candidate_commit is None and result.outcome == "succeeded"
    assert '"candidate_commit": null' in run.stdout


def test_run_refuses_unsandboxed_host_execution(tmp_path: Path, home: Path) -> None:
    data = profile_data()
    data["worker"] = {"allow_host_execution": False}
    _personal(home, data)
    run, _ = _invoke(tmp_path, "edit")
    assert run.exit_code == 2
    assert "allow_host_execution" in run.output
    assert not (home / ".maggy" / "worktrees").exists()  # refused before any worktree
