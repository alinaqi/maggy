"""Per-run budget flags: adapters that can cap their own spend get per_run_usd (RFC §2.6.4)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.launch import resolve_launch
from maggy.worker.models import WorkerSpec
from maggy.worker.pipeline import Attempt, run_attempt
from maggy.worker.templating import ArgvValues, render_argv
from maggy.worker.worktree import create_attempt_worktree
from worker_git_helpers import fake_adapter_data, init_repo, profile, write_script
from worker_helpers import adapter_data
from worker_launch_helpers import profile as launch_profile
from worker_launch_helpers import shipped

ARGV = ["fake", "{budget_flags}", "{permission_flags}", "{prompt}"]


def _adapter(**changes) -> AdapterSpec:
    data = {"argv": ARGV, "budget_flags": ["--max-budget-usd", "{budget_usd}"], **changes}
    return AdapterSpec.model_validate(adapter_data(**data))


def test_budget_flags_render_the_per_run_budget():
    values = ArgvValues(prompt="hi", workspace="/w", permission="workspace", budget_usd=0.25)
    assert render_argv(_adapter(), values) == ["fake", "--max-budget-usd", "0.2500", "hi"]


def test_no_budget_drops_budget_flags():
    values = ArgvValues(prompt="hi", workspace="/w", permission="workspace")
    assert render_argv(_adapter(), values) == ["fake", "hi"]


def test_budget_flags_only_accept_the_budget_placeholder():
    with pytest.raises(ValidationError, match="budget_flags"):
        _adapter(budget_flags=["--max-budget-usd", "{model}"])


def test_shipped_claude_caps_its_own_spend():
    plan = resolve_launch(shipped("claude"), launch_profile(), "read_only")
    argv = plan.argv(ArgvValues(prompt="p", workspace="/ws", permission="read_only",
                                budget_usd=0.25))
    assert argv[argv.index("--max-budget-usd") + 1] == "0.2500"


def test_pipeline_passes_per_run_budget_to_the_cli(tmp_path: Path):
    script = write_script(tmp_path, "echo", "import sys\nprint(' '.join(sys.argv[1:]))\n")
    data = fake_adapter_data(script)
    data.update(argv=[*data["argv"][:2], "{budget_flags}", "{prompt}"],
                budget_flags=["--budget", "{budget_usd}"])
    repo = tmp_path / "repo"
    repo.mkdir()
    spec = WorkerSpec(awg_ref="AWG-1", attempt_id="att-1", fencing_token="t", stage="build",
                      repo=repo, base_commit=init_repo(repo), spec_version=0,
                      workspace=tmp_path / "wt", permission="read_only", deadline_s=30,
                      budget_usd=0.3, prompt="noop")
    create_attempt_worktree(spec)
    attempt = Attempt(spec=spec, adapter=AdapterSpec.model_validate(data),
                      profile=profile(), state_dir=tmp_path / "state")
    result = run_attempt(attempt)
    assert Path(result.artifacts[0]).read_text().strip() == "--budget 0.3000 noop"
