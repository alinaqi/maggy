"""Phase 4 review fixes: annotations keyed the way the real `awg annotations` rows are
(`idempotency_key`), and plan children held under `stage:pending` until the plan gate."""

from __future__ import annotations

from pathlib import Path

from maggy.runner.awg_fake import FakeAwg
from maggy.runner.prompt import task_plan_of
from runner_plan_helpers import approve_plan, approved_rig, children, plan, task
from runner_spec_helpers import fenced

RISKY = plan(tasks=[task("T1", ["src/payments/charge.py"]), task("T2", ["src/h.py"], ["T1"])])
BUILD = ["maggy-runner", "stage:build", "project:demo"]


def test_fake_annotations_have_the_real_cli_row_shape() -> None:
    fake = FakeAwg()
    ref = fake.add_item("x", capabilities=["maggy-runner"])
    claim = fake.next_claim(["maggy-runner"])
    fake.annotate(claim, "k-1", {"a": 1})
    row = fake.annotations(ref)[0]
    assert row["idempotency_key"] == "k-1" and "key" not in row
    assert row["data"] == {"a": 1}


def test_task_plan_of_reads_the_idempotency_key() -> None:
    rows = [{"idempotency_key": "other", "data": {"x": 1}},
            {"idempotency_key": "task-plan", "data": {"key": "T1", "files": ["a.py"]}}]
    assert task_plan_of(rows) == {"key": "T1", "files": ["a.py"]}


class CapsAtCreate(FakeAwg):
    def __init__(self) -> None:
        super().__init__(lease_seconds=900)
        self.created: list[frozenset] = []
        self.ready_caps: list[frozenset] = []

    def create_child(self, claim, child) -> dict:
        self.created.append(frozenset(child.capabilities))
        return super().create_child(claim, child)

    def set_state(self, ref: str, state: str) -> dict:
        if state == "READY":
            self.ready_caps.append(self.items[ref].capabilities)
        return super().set_state(ref, state)


def test_children_are_created_under_a_stage_no_runner_holds(tmp_path: Path) -> None:
    spy = CapsAtCreate()
    rig = approved_rig(tmp_path, awg=spy)
    rig.author.queue([fenced(plan())])
    assert rig.runner.run_once().outcome == "planned"
    assert spy.created and all("stage:pending" in caps and "stage:build" not in caps
                               for caps in spy.created)
    assert spy.ready_caps == [frozenset(BUILD)] * 2


def test_waiting_children_cannot_be_claimed_by_a_build_runner(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path)
    rig.author.queue([fenced(RISKY)])
    assert rig.runner.run_once().outcome == "waiting_human"
    for child in children(rig):
        child.state = "READY"  # e.g. awg created it READY and the BACKLOG move never ran
        assert "stage:pending" in child.capabilities
    assert rig.awg.next_claim(BUILD) is None


def test_approved_plan_is_not_replanned_and_children_get_stage_build(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path)
    rig.author.queue([fenced(RISKY)])
    rig.runner.run_once()
    made = [c.ref for c in children(rig)]
    approve_plan(rig)
    assert rig.runner.run_once().outcome == "planned"
    assert [c.ref for c in children(rig)] == made and len(rig.author.prompts()) == 2
    assert all(c.capabilities == frozenset(BUILD) for c in children(rig))
