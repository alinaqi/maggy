"""Per-repo project binding (RFC §2.4, §2.6.8): a runner claims only its own project's items,
and `maggy run pause --project K` stops both claims and intake for K."""

from __future__ import annotations

from pathlib import Path

from maggy.runner.awg_fake import FakeAwg
from maggy.runner.config import claim_capabilities, project_capability
from maggy.runner.control import set_paused
from runner_loop_helpers import CAPS, EDIT_AGENT, make_rig


def test_project_capability_names_the_project() -> None:
    assert project_capability("shop") == "project:shop"
    caps, required = claim_capabilities("shop")
    assert caps == ["maggy-runner", "stage:spec", "stage:plan", "stage:build", "project:shop"] and required == ["maggy-runner", "project:shop"]


def test_runner_for_a_never_claims_project_b_items(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT, project="A", capabilities=[*CAPS, "project:B"])
    assert rig.runner.run_once().outcome == "idle"
    assert rig.awg.items[rig.ref].state == "READY"


def test_runner_never_claims_an_item_without_a_project(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT, project="A", capabilities=CAPS)
    assert rig.runner.run_once().outcome == "idle"
    assert rig.awg.items[rig.ref].state == "READY"


def test_runner_claims_its_own_project_items(tmp_path: Path) -> None:
    rig = make_rig(tmp_path, EDIT_AGENT, project="A", capabilities=[*CAPS, "project:A"])
    assert rig.runner.run_once().outcome == "submitted"


def test_pausing_b_leaves_runner_a_claiming_only_a(tmp_path: Path) -> None:
    awg = FakeAwg()
    other = awg.add_item("B work", capabilities=[*CAPS, "project:B"])
    rig = make_rig(tmp_path, EDIT_AGENT, awg=awg, project="A",
                   capabilities=[*CAPS, "project:A"])
    set_paused(rig.state, "B", True)
    report = rig.runner.run_once()
    assert (report.outcome, report.ref) == ("submitted", rig.ref)
    assert awg.items[other].state == "READY"
