"""Plan stage (RFC §2.4, §2.5): structured plan -> child TASKs, DEPENDS_ON, VALIDATIONs."""

from __future__ import annotations

from pathlib import Path

from maggy.runner.awg_errors import AwgError
from maggy.runner.awg_fake import FakeAwg
from maggy.runner.awg_types import Claim
from runner_plan_helpers import (
    approved_rig, children, entry, plan, requirement_ids, task,
)
from runner_spec_helpers import fenced

CHILD_CAPS = {"maggy-runner", "stage:build", "project:demo"}


def test_valid_plan_creates_children_deps_and_validations(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path)
    rig.author.queue([fenced(plan())])
    report = rig.runner.run_once()
    assert report.outcome == "planned"
    t1, t2 = children(rig)
    assert [t1.title, t2.title] == ["Task T1", "Task T2"]
    assert t1.capabilities == CHILD_CAPS == t2.capabilities
    assert t1.parent == rig.ref == t2.parent
    assert (t2.ref, "DEPENDS_ON", t1.ref) in rig.awg.edges
    reqs = requirement_ids(rig)
    assert [(v["kind"], v["min_trust"], v["requirement"]) for v in t1.validations] == [
        ("test", 3, reqs["AC1"])]
    assert [(v["kind"], v["min_trust"], v["requirement"]) for v in t2.validations] == [
        ("acceptance", 2, reqs["AC2"])]
    assert t1.state == "READY" == t2.state
    parent = rig.awg.items[rig.ref]
    assert "stage:plan" not in parent.capabilities and "stage:build" not in parent.capabilities
    assert parent.state == "READY"


class SpyAwg(FakeAwg):
    """Records each child's validations at the moment it is made READY."""

    def __init__(self) -> None:
        super().__init__(lease_seconds=900)
        self.ready_with: list[int] = []

    def set_state(self, ref: str, state: str) -> dict:
        if state == "READY":
            self.ready_with.append(len(self.items[ref].validations))
        return super().set_state(ref, state)


def test_children_become_ready_only_after_their_validations(tmp_path: Path) -> None:
    spy = SpyAwg()
    rig = approved_rig(tmp_path, awg=spy)
    rig.author.queue([fenced(plan())])
    assert rig.runner.run_once().outcome == "planned"
    assert spy.ready_with == [1, 1]
    assert all(c.state == "READY" for c in children(rig))


def _cyclic() -> dict:
    return plan(tasks=[task("T1", ["a.py"], ["T2"]), task("T2", ["b.py"], ["T1"])])


def test_cyclic_plan_retries_once_then_fails_without_graph(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path)
    rig.author.queue([fenced(_cyclic()), fenced(_cyclic())])
    report = rig.runner.run_once()
    assert report.outcome == "failed"
    assert children(rig) == [] and rig.awg.edges == []
    prompts = rig.author.prompts()
    assert len(prompts) == 3 and "rejected" in prompts[2] and "cycle" in prompts[2]
    assert "stage:plan" in rig.awg.items[rig.ref].capabilities


def test_missing_criterion_is_retried_and_can_succeed(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path)
    partial = plan(test_plan=[entry("AC1", "T1", ("unit", "test_export_writes_csv"))])
    rig.author.queue([fenced(partial), fenced(plan())])
    assert rig.runner.run_once().outcome == "planned"
    assert "AC2" in rig.author.prompts()[2]


def test_unknown_dependency_and_outside_files_are_rejected(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path)
    bad_dep = plan(tasks=[task("T1", ["a.py"], ["T9"]), task("T2", ["b.py"])])
    outside = plan(tasks=[task("T1", ["../etc/passwd"]), task("T2", ["/abs.py"])])
    rig.author.queue([fenced(bad_dep), fenced(outside)])
    assert rig.runner.run_once().outcome == "failed"
    assert "T9" in rig.author.prompts()[2] and children(rig) == []


class BrokenLinkAwg(FakeAwg):
    def link(self, claim: Claim, edge) -> dict:
        raise AwgError("dependency_cycle", "cycle")


def test_mid_build_failure_cancels_the_partial_children(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path, awg=BrokenLinkAwg(lease_seconds=900))
    rig.author.queue([fenced(plan())])
    assert rig.runner.run_once().outcome == "failed"
    assert [c.state for c in children(rig)] == ["CANCELLED", "CANCELLED"]
    assert "stage:plan" in rig.awg.items[rig.ref].capabilities
