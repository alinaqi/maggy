"""Plan gates (RFC §2.5): high-risk paths wait for a human `plan-approved` DECISION before
any child is READY; an approved (or low-risk) plan makes its children READY and parks the
parent as `stage:planned`; a stale spec sends the item back to `stage:spec`."""

from __future__ import annotations

from fnmatch import fnmatchcase

from maggy.harness.schema import HarnessProfile
from maggy.runner.awg_types import WorkUpdate
from maggy.runner.session import RunReport, Session
from maggy.runner.stages.plan_models import Plan
from maggy.runner.stages.spec_gate import with_stage
from maggy.runner.stages.spec_version import latest
from maggy.worker.protected import protected_paths

PLAN_APPROVED = "plan-approved"
PLANNED, SPEC = "stage:planned", "stage:spec"
PENDING, BUILD = "stage:pending", "stage:build"  # children: held, then released to build


def risky_files(plan: Plan, profile: HarnessProfile, risk_paths: list[str]) -> list[str]:
    """Planned files under risk.high (or always-protected) paths or the spec's risk paths."""
    files = sorted({f for task in plan.tasks for f in task.files})
    flagged = [f for f in files if any(_matches(f, pattern) for pattern in risk_paths)]
    return sorted({*protected_paths(files, profile), *flagged})


def _matches(path: str, pattern: str) -> bool:
    prefix = pattern.rstrip("/") + "/"
    return path == pattern or fnmatchcase(path, pattern) or path.startswith(prefix)


def plan_approved(decisions: list[dict], key: str) -> bool:
    approval = latest(decisions, PLAN_APPROVED)
    return approval is not None and (approval.get("data") or {}).get("plan") == key


def wait_for_approval(session: Session, key: str, record: dict) -> RunReport:
    ref = session.claim.ref
    summary = (f"Plan {key} touches high-risk path(s): {', '.join(record['risky'])}. "
               f"Children {', '.join(record['children'])} stay in BACKLOG until approved. To "
               f"approve: awg decision {ref} --key {PLAN_APPROVED} --title 'plan approved' "
               f"--data '{{\"plan\": \"{key}\"}}', then move {ref} to READY.")
    session.verify()
    session.awg.block(session.claim, summary, human=True)
    session.log("plan_waiting_approval", {"plan": key, "risky": record["risky"]})
    return session.report("waiting_human", summary)


def finish(session: Session, shown: dict, children: list[str]) -> RunReport:
    """Each child gets `stage:build` (it was held under `stage:pending`), then READY."""
    build = with_stage(shown, BUILD)
    for ref in children:
        session.verify()
        session.awg.set_capabilities(ref, build)
        session.awg.set_state(ref, "READY")
    return _hand_to(session, (shown, PLANNED, f"planned: {', '.join(children)} READY"),
                    "planned")


def back_to_spec(session: Session, shown: dict) -> RunReport:
    reason = "acceptance criteria changed since spec approval; back to the spec stage"
    return _hand_to(session, (shown, SPEC, reason), "spec_stale")


def _hand_to(session: Session, move: tuple[dict, str, str], outcome: str) -> RunReport:
    shown, stage, reason = move
    session.verify()
    session.awg.update(session.claim, WorkUpdate(capabilities=with_stage(shown, stage)))
    session.verify()
    session.awg.release(session.claim, reason)
    session.log(outcome, {"stage": stage, "reason": reason})
    return session.report(outcome, reason)
