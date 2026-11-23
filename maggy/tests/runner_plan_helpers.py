"""Plan-stage rigs: the real spec stage approves a spec first, then the plan stage runs.

The author agent (agents.default) answers the spec draft, then the plan; the reviewer agent
answers the spec review. Replies are recorded (see runner_spec_helpers.Agent).
"""

from __future__ import annotations

from pathlib import Path

from maggy.runner.awg_fake import FakeAwg
from runner_spec_helpers import SpecRig, draft, fenced, make_spec_rig, review

CRITERIA = ("Export writes CSV", "CSV has a header row")


def task(key: str, files: list[str], depends_on: list[str] | None = None) -> dict:
    return {"key": key, "title": f"Task {key}", "description": f"Do {key}.", "files": files,
            "depends_on": depends_on or []}


def entry(criterion: str, key: str, proof: tuple[str, str]) -> dict:
    """A test-plan entry; `proof` is (evidence kind, regression test name)."""
    evidence, test_name = proof
    return {"criterion_id": criterion, "task": key, "fixture": f"fixture for {criterion}",
            "action": f"run {key}", "expected": f"{criterion} holds", "evidence": evidence,
            "regression_test_name": test_name}


def plan(tasks: list[dict] | None = None, test_plan: list[dict] | None = None) -> dict:
    return {"tasks": tasks if tasks is not None else [
                task("T1", ["src/export.py"]), task("T2", ["src/header.py"], ["T1"])],
            "test_plan": test_plan if test_plan is not None else [
                entry("AC1", "T1", ("unit", "test_export_writes_csv")),
                entry("AC2", "T2", ("manual", "test_header_row_present"))]}


def approved_rig(tmp_path: Path, awg: FakeAwg | None = None,
                 risk_paths: list[str] | None = None) -> SpecRig:
    """A rig whose item went through the real spec stage and now carries `stage:plan`."""
    rig = make_spec_rig(tmp_path)
    if awg is not None:
        awg.items, awg.nodes = rig.awg.items, rig.awg.nodes
        rig.runner.awg, rig.awg = awg, awg
    spec = {**draft(*CRITERIA), "risk_paths": risk_paths or []}
    rig.author.queue([fenced(spec)])
    rig.reviewer.queue([fenced(review("ready"))])
    assert rig.runner.run_once().outcome == "spec_approved"
    return rig


def children(rig: SpecRig) -> list:
    return [item for ref, item in rig.awg.items.items() if ref != rig.ref]


def requirement_ids(rig: SpecRig) -> dict[str, str]:
    """criterion id -> REQUIREMENT node id."""
    return {n["data"]["id"]: n["id"] for n in rig.awg.nodes if n["type"] == "REQUIREMENT"}


def approve_plan(rig: SpecRig) -> None:
    """A human records the plan-approved DECISION named in the summary and moves it READY."""
    key = [a["key"] for a in rig.awg.items[rig.ref].annotations if a["key"].startswith("plan-")]
    rig.awg.nodes.append({"id": f"N-{len(rig.awg.nodes) + 1}", "type": "DECISION",
                          "key": "plan-approved", "data": {"plan": key[-1]}, "parent": rig.ref})
    rig.awg.items[rig.ref].state = "READY"
