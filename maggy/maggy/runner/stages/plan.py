"""The plan stage (RFC §2.4, §2.5) for items claimed with `stage:plan`.

The spec must still be the approved one (else back to `stage:spec`). A read-only planner
returns a structured Plan, checked as a DAG covering every criterion (one retry, then the
stage fails before any graph mutation). Its children, links and validations are built in
BACKLOG and recorded in a `plan-<criteria sha>` annotation, so a re-claim never re-plans;
high-risk plans wait for a human `plan-approved` DECISION before any child is READY.
"""

from __future__ import annotations

from maggy.runner.attempt import workspace_for
from maggy.runner.session import RunReport, Session
from maggy.runner.stages.plan_gate import (
    back_to_spec, finish, plan_approved, risky_files, wait_for_approval,
)
from maggy.runner.stages.plan_graph import Blueprint, build_graph
from maggy.runner.stages.plan_models import Plan, checked_plan
from maggy.runner.stages.plan_prompt import plan_prompt
from maggy.runner.stages.spec_gate import with_stage
from maggy.runner.stages.spec_prompt import SpecContext
from maggy.runner.stages.spec_version import (
    SPEC_APPROVED, criteria_sha, criterion_ids, latest, spec_is_current,
)
from maggy.runner.stages.structured import ask_structured
from maggy.runner.stages.worker import StageWorkers
from maggy.runner.workspace import prepare_workspace


def run_plan(session: Session, shown: dict) -> RunReport:
    session.verify()
    claim, awg = session.claim, session.awg
    decisions = awg.decisions(claim.ref)
    approval = latest(decisions, SPEC_APPROVED)
    if not spec_is_current(approval, claim.acceptance_criteria):
        return back_to_spec(session, shown)
    key = f"plan-{criteria_sha(claim.acceptance_criteria)[:12]}"
    record = _recorded(awg.annotations(claim.ref), key)
    if record is None:
        risk_paths = list(((approval or {}).get("data") or {}).get("risk_paths") or [])
        record = _make_plan(session, shown, (key, risk_paths))
    if record["risky"] and not plan_approved(decisions, key):
        return wait_for_approval(session, key, record)
    return finish(session, shown, record["children"])


def _recorded(annotations: list[dict], key: str) -> dict | None:
    found = [a.get("data") or {} for a in annotations if a.get("key") == key]
    return found[0] if found else None


def _make_plan(session: Session, shown: dict, job: tuple[str, list[str]]) -> dict:
    key, risk_paths = job
    plan = _ask_planner(session, shown, risk_paths)
    blueprint = Blueprint(plan, _requirements(session), with_stage(shown, "stage:build"))
    children = build_graph(session, blueprint)
    record = {"children": children, "risky": risky_files(plan, session.config.profile, risk_paths),
              "tasks": [t.key for t in plan.tasks]}
    session.verify()
    session.awg.annotate(session.claim, key, record)
    session.log("plan_built", {"plan": key, **record})
    return record


def _ask_planner(session: Session, shown: dict, risk_paths: list[str]) -> Plan:
    claim, repo = session.claim, session.config.repo
    base = prepare_workspace(repo, workspace_for(session), claim.ref)
    workers = StageWorkers(session, "plan", (workspace_for(session), base))
    model = checked_plan(list(criterion_ids(claim.acceptance_criteria)), repo)
    prompt = plan_prompt(SpecContext(claim, shown, repo), risk_paths)
    plan = ask_structured(lambda p: workers.ask("plan", p), prompt, model)
    session.log("plan_drafted", {"tasks": len(plan.tasks), "entries": len(plan.test_plan)})
    return plan


def _requirements(session: Session) -> dict[str, str]:
    """criterion id -> REQUIREMENT node id (by the node's criterion id, else its title)."""
    texts = criterion_ids(session.claim.acceptance_criteria)
    by_text = {text: cid for cid, text in texts.items()}
    nodes = session.awg.requirements(session.claim.ref)
    return {(n.get("criterion") or by_text.get(n.get("title", ""), "")): str(n["id"])
            for n in nodes if n.get("criterion") or n.get("title") in by_text}
