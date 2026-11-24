"""Build the plan's graph under the claimed item (RFC §2.4): child TASKs in BACKLOG carrying
their task plan, DEPENDS_ON links, then one VALIDATION per test-plan entry on its task,
linked to the criterion's REQUIREMENT node. Any failure cancels the children made so far,
so a failed plan never leaves a partial graph that could become claimable."""

from __future__ import annotations

from dataclasses import dataclass

from maggy.runner.awg_errors import AwgError
from maggy.runner.awg_types import ChildSpec, EdgeSpec, ValidationSpec
from maggy.runner.session import Session
from maggy.runner.stages.plan_models import Plan, PlanTask, TestPlanEntry


@dataclass(frozen=True)
class Blueprint:
    plan: Plan
    requirements: dict[str, str]  # criterion id -> REQUIREMENT node id
    capabilities: list[str]  # the children's: maggy-runner, stage:pending, project


def build_graph(session: Session, blueprint: Blueprint) -> list[str]:
    """The children's refs in plan order (still BACKLOG)."""
    made: dict[str, str] = {}
    try:
        _children(session, blueprint, made)
        _links(session, blueprint.plan, made)
        _validations(session, blueprint, made)
    except Exception:
        _cancel(session, list(made.values()))
        raise
    return [made[task.key] for task in blueprint.plan.tasks]


def task_plan(task: PlanTask, entries: list[TestPlanEntry]) -> dict:
    return {"key": task.key, "description": task.description, "files": task.files,
            "test_plan": [e.model_dump() for e in entries if e.task == task.key]}


def _children(session: Session, blueprint: Blueprint, made: dict[str, str]) -> None:
    for task in blueprint.plan.tasks:
        child = ChildSpec(title=task.title, capabilities=blueprint.capabilities,
                          plan=task_plan(task, blueprint.plan.test_plan))
        session.verify()
        made[task.key] = str(session.awg.create_child(session.claim, child)["display_id"])


def _links(session: Session, plan: Plan, made: dict[str, str]) -> None:
    edges = [EdgeSpec(source=made[t.key], type="DEPENDS_ON", target=made[dep])
             for t in plan.tasks for dep in t.depends_on]
    for edge in edges:
        session.verify()
        session.awg.link(session.claim, edge)


def _validations(session: Session, blueprint: Blueprint, made: dict[str, str]) -> None:
    for entry in blueprint.plan.test_plan:
        kind, trust = entry.validation()
        title = f"[{entry.criterion_id}] {entry.regression_test_name}: {entry.expected}"
        spec = ValidationSpec(work=made[entry.task], kind=kind, title=title[:200],
                              min_trust=trust,
                              requirement=blueprint.requirements.get(entry.criterion_id))
        session.verify()
        session.awg.add_validation(session.claim, spec)


def _cancel(session: Session, refs: list[str]) -> None:
    for ref in refs:
        try:
            session.awg.set_state(ref, "CANCELLED")
        except AwgError as exc:
            session.log("awg_error", {"error": str(exc), "cancel": ref})
    session.log("plan_rolled_back", {"children": refs})
