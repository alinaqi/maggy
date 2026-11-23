"""Phase 3 exit: intake -> `maggy run --once` against the REAL awg CLI, then kill -9 + restart.

Skips (with the reason) only when no awg CLI with the runner flags is available.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path

import pytest
from runner_exit_gh import issue
from runner_exit_helpers import ExitRig, find_awg, make_exit_rig
from runner_publish_helpers import remote_head

from maggy.harness.cli.awg_tokens import ensure_awg
from maggy.harness.cli.env import ToolEnv

AWG_BIN, SKIP_REASON = find_awg()
pytestmark = pytest.mark.skipif(AWG_BIN is None, reason=f"real awg unavailable: {SKIP_REASON}")
RUNNER_CAPS = ["--capability", "maggy-runner", "--capability", "stage:build"]


@pytest.fixture
def rig(tmp_path: Path, monkeypatch) -> ExitRig:
    rig, env = make_exit_rig(tmp_path, AWG_BIN)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AWG_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    notes, problems = ensure_awg(ToolEnv(home=rig.home), [])
    assert not problems, problems
    assert rig.token("runner-agent").is_file() and rig.token("runner-ci").is_file()
    return rig


def _run_once(rig: ExitRig) -> list[str]:
    done = rig.maggy("run", "--once", "--repo", str(rig.repo), "--awg-bin", str(rig.awg_bin))
    assert done.returncode == 0, done.stderr
    return done.stdout.strip().split("\t")


def _test_validation(proof: dict) -> dict:
    [check] = [v for v in proof["validations"] if v["kind"] == "test"]
    return check


def _assert_published(rig: ExitRig, ref: str, sha: str) -> dict:
    """CI-trust evidence bound to `sha`, maggy/<ref> at `sha`, one draft PR, one submit."""
    proof = rig.awg("proof", ref, "--json", token="runner-agent")
    check = _test_validation(proof)
    assert check["status"] == "PASS" and check["min_trust"] == 3
    [evidence] = [e for e in check["evidence"] if e["producer"] == "maggy-runner-ci"]
    assert (evidence["trust_class"], evidence["commit_sha"]) == (3, sha)
    assert evidence["fresh"], "evidence must be bound to the submitted revision"
    assert remote_head(rig.remote, ref) == sha
    [pr] = rig.gh.prs()
    assert rig.gh.creates() == 1 and pr["isDraft"] and pr["head"] == f"maggy/{ref}"
    submitted = [a for a in proof["attempts"] if a["state"] == "COMPLETED"]
    assert len(submitted) == 1, proof["attempts"]
    expected = "DONE" if proof["verdict"] == "PASS" else "VERIFYING"
    assert proof["work"]["state"] == expected and proof["work"]["revision_sha"] == sha
    return proof


def test_intake_then_run_once_publishes_with_ci_evidence(rig: ExitRig) -> None:
    rig.gh.issues([issue(1, ["factory"]), issue(2, ["question"])])
    done = rig.maggy("run", "intake", "--repo", "acme/shop", "--label", "factory",
                     "--awg-bin", str(rig.awg_bin), "--checkout", str(rig.repo))
    assert done.returncode == 0, done.stderr
    [item] = rig.awg("list", "--json")["items"]
    ref = item["display_id"]
    assert ref in done.stdout and item["execution_policy"]["capabilities"] == [
        "maggy-runner", "stage:build"]
    outcome, reported, sha = _run_once(rig)
    assert (outcome, reported) == ("submitted", ref)
    _assert_published(rig, ref, sha)
    assert _run_once(rig)[0] == "idle"


def test_agent_token_evidence_does_not_satisfy_the_ci_validation(rig: ExitRig) -> None:
    created = rig.awg("create", "Add feature", "--ac", "feature.txt exists", *RUNNER_CAPS,
                      "--json")
    ref = created["display_id"]
    outcome, _, sha = _run_once(rig)
    assert outcome == "submitted"
    check = _test_validation(rig.awg("proof", ref, "--json"))
    rig.awg("evidence", ref, "--kind=test", "--verdict=FAIL", f"--commit-sha={sha}",
            f"--validation={check['id']}", "--json", token="runner-agent")
    after = _test_validation(rig.awg("proof", ref, "--json"))
    assert after["status"] == "PASS", "agent-trust evidence must not move a CI validation"
    assert sorted(e["trust_class"] for e in after["evidence"]) == [1, 3]
    proof = _assert_published(rig, ref, sha)
    assert proof["work"]["state"] == "VERIFYING"  # the acceptance criterion needs review


def _wait_for(path: Path, proc: subprocess.Popen, timeout_s: float = 180) -> None:
    deadline = time.monotonic() + timeout_s
    while not path.exists():
        assert proc.poll() is None, proc.communicate()
        assert time.monotonic() < deadline, f"timed out waiting for {path.name}"
        time.sleep(0.2)


def test_sigkill_after_push_then_restart_converges(rig: ExitRig) -> None:
    ref = rig.awg("create", "Add feature", "--ac", "feature.txt exists", *RUNNER_CAPS,
                  "--json")["display_id"]
    (rig.gh.root / "hold").write_text("hold\n")
    argv = rig.maggy_argv("run", "--once", "--repo", str(rig.repo), "--awg-bin", str(rig.awg_bin))
    proc = subprocess.Popen(argv, cwd=rig.root, start_new_session=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    _wait_for(rig.gh.root / "holding", proc)
    pushed = remote_head(rig.remote, ref)
    assert pushed, "the runner was killed before it pushed"
    os.killpg(proc.pid, signal.SIGKILL)
    proc.wait(timeout=30)
    state = json.loads((rig.home / ".maggy" / "runner" / "state.json").read_text())
    assert list(state["held"]) == [ref] and rig.gh.prs() == []
    (rig.gh.root / "hold").unlink()
    outcome, reported, sha = _run_once(rig)
    assert (outcome, reported, sha) == ("submitted", ref, pushed)
    assert _run_once(rig)[0] == "idle"
    _assert_published(rig, ref, sha)
