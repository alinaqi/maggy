"""A parent item at `stage:verify` with an approved spec, a plan record and one DONE build
child whose branch carries the fix: what the verify stage finds after the build stage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from maggy.harness.schema import HarnessProfile
from maggy.review.models import Verdict
from maggy.runner.awg_fake import FakeAwg
from maggy.runner.loop import Runner, RunnerConfig
from maggy.runner.stages.spec_version import criteria_sha
from regression_helpers import CALC_BUGGY, PYTEST, commit_all, write_files
from worker_git_helpers import (DUMP_CHECK, dump_command, fake_adapter, git, init_repo,
                                profile_data, write_script)

CRITERIA = ["[AC1] add returns the sum", "[AC3] message sits under the coupon field"]
CAPS = ["maggy-runner", "stage:verify", "project:demo"]


class ApprovingCouncil:
    """A review council with no findings (the rig's default: a council must be wired in)."""

    def review(self, request: object) -> Verdict:
        return Verdict(decision="approve", summary="ok")


@dataclass
class VerifyRig:
    runner: Runner
    awg: FakeAwg
    ref: str
    child: str
    repo: Path
    state: Path
    check_out: Path


def make_verify_rig(tmp_path: Path, child: tuple[list[dict], dict[str, str]],
                    **options) -> VerifyRig:
    """`child`: the build child's (test plan entries, files on its branch); `options`:
    vision (backends), council (default: approves), base_files, check_exit."""
    entries, child_files = child
    repo, awg = tmp_path / "repo", FakeAwg(lease_seconds=900)
    repo.mkdir()
    init_repo(repo)
    write_files(repo, {"calc.py": CALC_BUGGY, **options.get("base_files", {})})
    commit_all(repo, "base")
    criteria = covered(entries)
    ref = awg.add_item("Fix expired coupons", CAPS, criteria)
    task = awg.add_item("T1", ["maggy-runner", "stage:build", "project:demo"])
    _branch(repo, f"maggy/{task}", child_files)
    _plan(awg, (ref, task), (criteria, entries))
    config = _config(tmp_path, options)
    return VerifyRig(Runner(awg, config), awg, ref, task, repo, tmp_path / "state",
                     tmp_path / "check.json")


def _branch(repo: Path, branch: str, files: dict[str, str]) -> None:
    git(repo, "checkout", "-q", "-b", branch)
    write_files(repo, files)
    commit_all(repo, "child work")
    git(repo, "checkout", "-q", "main")


def covered(entries: list[dict]) -> list[str]:
    """The criteria the test plan covers (a plan that passed the plan check covers all)."""
    ids = {str(e["criterion_id"]) for e in entries}
    return [c for c in CRITERIA if c[1:4] in ids] or CRITERIA


def _plan(awg: FakeAwg, refs: tuple[str, str], plan: tuple[list[str], list[dict]]) -> None:
    (ref, child), (criteria, entries) = refs, plan
    sha = criteria_sha(criteria)
    ids = [c[1:4] for c in criteria]
    awg.nodes.append({"id": "N-1", "type": "DECISION", "key": "spec-approved", "parent": ref,
                      "data": {"criteria_sha": sha, "criteria": ids}})
    awg.items[ref].annotations.append({"key": f"plan-{sha[:12]}", "data": {
        "children": [child], "risky": [], "tasks": ["T1"]}})
    item = awg.items[child]
    item.state, item.parent = "DONE", ref
    item.annotations.append({"key": "task-plan", "data": {"key": "T1", "test_plan": entries}})


def _config(tmp_path: Path, options: dict) -> RunnerConfig:
    check = dump_command(write_script(tmp_path, "dump", DUMP_CHECK), tmp_path / "check.json",
                         options.get("check_exit", 0))
    data = profile_data({"test": check}, ["test"])
    data["validation"]["regression"] = {"runner": "pytest", "command": PYTEST}
    data["worker"]["stages"] = ["verify"]
    return RunnerConfig(repo=tmp_path / "repo", state_dir=tmp_path / "state",
                        adapter=fake_adapter(write_script(tmp_path, "agent", "pass")),
                        profile=HarnessProfile.model_validate(data), project="demo",
                        heartbeat_s=30.0, vision=options.get("vision", []),
                        council=options.get("council", ApprovingCouncil()))


def approve_baselines(rig: VerifyRig) -> list[str]:
    """A human records one baseline-approved DECISION per proposed image, then READY."""
    item = rig.awg.items[rig.ref]
    proposals = [a for a in item.annotations if a["key"].startswith("baseline-proposed:")]
    keys = []
    for proposal in proposals:
        data = proposal["data"]
        key = f"baseline-approved:{data['criterion_id']}:{data['viewport']}"
        rig.awg.nodes.append({"id": f"N-{len(rig.awg.nodes) + 1}", "type": "DECISION",
                              "key": key, "data": {"sha256": data["sha256"]},
                              "parent": rig.ref})
        keys.append(key)
    item.state = "READY"
    return keys


def verify_record(rig: VerifyRig, sha: str) -> dict | None:
    """The latest `verify-<sha>:<attempt>` record the verify stage annotated."""
    found = [a["data"] for a in rig.awg.items[rig.ref].annotations
             if a["key"].startswith(f"verify-{sha}:")]
    return found[-1] if found else None
