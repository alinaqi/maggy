"""A planned parent moves to `stage:verify` when its last build child is about to be
submitted (RFC §2.5: build -> verify without a human retagging the parent)."""

from __future__ import annotations

from pathlib import Path

from maggy.runner.awg_fake import FakeAwg
from maggy.runner.config import RunnerConfig
from maggy.runner.session import Session
from maggy.runner.stages.advance import advance_parent
from maggy.runner.stages.plan_graph import Blueprint, build_graph
from maggy.runner.stages.plan_models import Plan
from maggy.runner.stages.spec_version import criteria_sha
from worker_git_helpers import fake_adapter, profile, write_script

CRITERIA = ["[AC1] expired coupons show an error"]
PLANNED = ["maggy-runner", "project:demo", "stage:planned"]
BUILD = ["maggy-runner", "project:demo", "stage:build"]


def _rig(tmp_path: Path, parent_caps: list[str] = PLANNED) -> tuple[FakeAwg, str, list[str]]:
    awg = FakeAwg(lease_seconds=900)
    parent = awg.add_item("Fix coupons", parent_caps, CRITERIA)
    children = [awg.add_item(f"T{n}", BUILD) for n in (1, 2)]
    awg.items[parent].annotations.append({"key": f"plan-{criteria_sha(CRITERIA)[:12]}",
                                          "data": {"children": children, "risky": []}})
    for ref in children:
        awg.items[ref].parent, awg.items[ref].state = parent, "BACKLOG"
        awg.items[ref].annotations.append({"key": "task-plan", "data": {"parent": parent}})
    return awg, parent, children


def _session(tmp_path: Path, awg: FakeAwg, ref: str) -> Session:
    awg.items[ref].state = "READY"
    claim = awg.next_claim(sorted(awg.items[ref].capabilities))
    assert claim is not None and claim.ref == ref
    config = RunnerConfig(repo=tmp_path, state_dir=tmp_path / "state", profile=profile(),
                          adapter=fake_adapter(write_script(tmp_path, "agent", "pass")))
    return Session(awg, claim, config)


def _caps(awg: FakeAwg, ref: str) -> list[str]:
    return sorted(awg.items[ref].capabilities)


def test_last_child_moves_the_parent_to_verify(tmp_path: Path) -> None:
    awg, parent, (first, last) = _rig(tmp_path)
    awg.items[first].state = "VERIFYING"
    assert advance_parent(_session(tmp_path, awg, last)) == parent
    assert _caps(awg, parent) == ["maggy-runner", "project:demo", "stage:verify"]


def test_parent_waits_while_a_sibling_is_unfinished(tmp_path: Path) -> None:
    awg, parent, (first, last) = _rig(tmp_path)
    assert advance_parent(_session(tmp_path, awg, last)) is None
    assert _caps(awg, parent) == PLANNED


def test_parent_not_parked_as_planned_is_left_alone(tmp_path: Path) -> None:
    caps = ["maggy-runner", "project:demo", "stage:plan"]
    awg, parent, (first, last) = _rig(tmp_path, caps)
    awg.items[first].state = "DONE"
    assert advance_parent(_session(tmp_path, awg, last)) is None
    assert _caps(awg, parent) == caps


def test_items_without_a_planned_parent_are_untouched(tmp_path: Path) -> None:
    awg = FakeAwg(lease_seconds=900)
    ref = awg.add_item("Standalone", BUILD)
    assert advance_parent(_session(tmp_path, awg, ref)) is None


def test_plan_graph_records_the_parent_in_each_task_plan(tmp_path: Path) -> None:
    awg = FakeAwg(lease_seconds=900)
    parent = awg.add_item("Fix coupons", ["maggy-runner", "project:demo", "stage:plan"],
                          CRITERIA)
    session = _session(tmp_path, awg, parent)
    entry = {"criterion_id": "AC1", "task": "T1", "fixture": "cart", "action": "apply",
             "expected": "error", "evidence": "unit", "regression_test_name": "test_ac1"}
    plan = Plan.model_validate({"tasks": [{"key": "T1", "title": "Fix"}], "test_plan": [entry]})
    [child] = build_graph(session, Blueprint(plan, {}, BUILD))
    [note] = [a for a in awg.items[child].annotations if a["key"] == "task-plan"]
    assert note["data"]["parent"] == parent
