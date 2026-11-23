"""Plan gates: high-risk paths wait for plan approval; a stale spec goes back to stage:spec;
the build stage prompt carries the task's test plan (RFC §2.4, §2.5)."""

from __future__ import annotations

from pathlib import Path

from runner_plan_helpers import approve_plan, approved_rig, children, plan, task
from runner_spec_helpers import fenced

RISKY = plan(tasks=[task("T1", ["src/payments/charge.py"]), task("T2", ["src/h.py"], ["T1"])])


def test_high_risk_path_waits_for_plan_approval(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path)
    rig.author.queue([fenced(RISKY)])
    report = rig.runner.run_once()
    parent = rig.awg.items[rig.ref]
    assert report.outcome == "waiting_human" and parent.state == "WAITING_HUMAN"
    assert any("src/payments/charge.py" in c["body"] and "plan-approved" in c["body"]
               for c in parent.comments)
    assert len(children(rig)) == 2
    assert all(c.state == "BACKLOG" and c.validations for c in children(rig))


def test_without_approval_children_stay_backlog(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path)
    rig.author.queue([fenced(RISKY)])
    rig.runner.run_once()
    rig.awg.items[rig.ref].state = "READY"  # moved back without a decision
    report = rig.runner.run_once()
    assert report.outcome == "waiting_human"
    assert all(c.state == "BACKLOG" for c in children(rig)) and len(children(rig)) == 2
    assert len(rig.author.prompts()) == 2  # no re-plan


def test_plan_approved_decision_releases_the_children(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path)
    rig.author.queue([fenced(RISKY)])
    rig.runner.run_once()
    approve_plan(rig)
    assert rig.runner.run_once().outcome == "planned"
    assert [c.state for c in children(rig)] == ["READY", "READY"]
    assert len(rig.author.prompts()) == 2


def test_spec_flagged_risk_path_needs_approval(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path, risk_paths=["src/export.py"])
    rig.author.queue([fenced(plan())])
    assert rig.runner.run_once().outcome == "waiting_human"
    assert all(c.state == "BACKLOG" for c in children(rig))


def test_stale_spec_goes_back_to_spec_stage(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path)
    rig.awg.items[rig.ref].acceptance_criteria = ["[AC1] Export writes JSON"]
    report = rig.runner.run_once()
    parent = rig.awg.items[rig.ref]
    assert report.outcome == "spec_stale" and parent.state == "READY"
    assert "stage:spec" in parent.capabilities and "stage:plan" not in parent.capabilities
    assert children(rig) == [] and len(rig.author.prompts()) == 1


def test_build_prompt_carries_the_task_test_plan(tmp_path: Path) -> None:
    rig = approved_rig(tmp_path)
    rig.author.queue([fenced(plan())])
    assert rig.runner.run_once().outcome == "planned"
    rig.runner.run_once()  # claims T1 (T2 waits on it) as a build
    prompt = rig.author.prompts()[-1]
    assert "Task T1" in prompt and "Test plan" in prompt
    assert "test_export_writes_csv" in prompt and "fixture for AC1" in prompt
    assert "AC1 holds" in prompt and "test_header_row_present" not in prompt
