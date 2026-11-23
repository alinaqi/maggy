"""Kill switch after the worker ends, and a CLI's own budget stop (RFC §2.6.4, §2.6.8)."""

from __future__ import annotations

from pathlib import Path

from maggy.worker.adapter_spec import AdapterSpec
from maggy.worker.models import WorkerSpec
from maggy.worker.pipeline import Attempt, run_attempt
from maggy.worker.worktree import create_attempt_worktree
from worker_fixture_helpers import FIXTURES
from worker_git_helpers import (DUMP_CHECK, dump_command, fake_adapter_data, git, init_repo,
                                profile, write_script)

# Writes candidate code, then pulls the kill switch (path = argv[-1]) before exiting 0.
STOPPING_AGENT = """
import sys
from pathlib import Path
Path("evil.py").write_text("print('pwned')\\n")
Path(sys.argv[-1]).parent.mkdir(parents=True, exist_ok=True)
Path(sys.argv[-1]).write_text("stop\\n")
"""

# Replays the recorded Claude budget-cap result (argv[1]) and exits 1, like claude does.
REPLAY_ERROR = """
import sys
from pathlib import Path
print(Path(sys.argv[1]).read_text())
sys.exit(1)
"""


def _attempt(tmp_path: Path, adapter: AdapterSpec, prompt: str) -> tuple[Attempt, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    spec = WorkerSpec(awg_ref="AWG-7", attempt_id="att-7", fencing_token="local", stage="build",
                      repo=repo, base_commit=init_repo(repo), spec_version=0,
                      workspace=tmp_path / "wt", permission="workspace", deadline_s=30,
                      budget_usd=0.25, prompt=prompt)
    create_attempt_worktree(spec)
    out = tmp_path / "dump.json"
    command = dump_command(write_script(tmp_path, "dump", DUMP_CHECK), out)
    prof = profile(commands={"test": command}, required=["test"])
    return Attempt(spec=spec, adapter=adapter, profile=prof, state_dir=tmp_path / "state"), out


def test_stop_during_run_skips_commit_and_checks(tmp_path: Path) -> None:
    script = write_script(tmp_path, "agent", STOPPING_AGENT)
    adapter = AdapterSpec.model_validate(fake_adapter_data(script))
    attempt, out = _attempt(tmp_path, adapter, str(tmp_path / "state" / "STOP"))
    result = run_attempt(attempt)
    assert result.outcome == "failed"
    assert result.candidate_commit is None and result.checks == []
    assert not out.exists(), "a check ran after STOP"
    assert git(attempt.spec.workspace, "rev-parse", "HEAD") == attempt.spec.base_commit


def test_claude_budget_cap_is_budget_exceeded(tmp_path: Path) -> None:
    script = write_script(tmp_path, "claude_fake", REPLAY_ERROR)
    data = fake_adapter_data(script)
    data.update(output="claude-json", argv=[*data["argv"][:2], str(FIXTURES / "claude" / "error.json"),
                                             "{prompt}"])
    attempt, _ = _attempt(tmp_path, AdapterSpec.model_validate(data), "noop")
    result = run_attempt(attempt)
    assert result.outcome == "budget_exceeded"
    assert result.cost_usd == 0.00171252
