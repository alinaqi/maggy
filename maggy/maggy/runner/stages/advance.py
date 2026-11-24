"""Hand a planned parent to the verify stage (RFC §2.5: build -> verify).

The plan stage parks the parent as `stage:planned` and records its ref in each child's
`task-plan` annotation. Just before a build child is submitted (while its lease is still
live, so the change is fenced), the runner re-tags the parent `stage:verify` when every
OTHER child of the parent's plan record is already finished. If that submit then fails, the
verify stage finds an unfinished child and gives the parent back (`waiting_children`).
"""

from __future__ import annotations

from maggy.runner.awg_types import annotation_data
from maggy.runner.prompt import task_plan_of
from maggy.runner.session import Session
from maggy.runner.stages.plan_gate import PLANNED
from maggy.runner.stages.spec_gate import with_stage
from maggy.runner.stages.spec_version import criteria_sha
from maggy.runner.stages.verify import FINISHED

VERIFY = "stage:verify"


def advance_parent(session: Session) -> str | None:
    """The parent's ref when it was moved to `stage:verify`, else None."""
    awg, me = session.awg, session.claim.ref
    parent = str(task_plan_of(awg.annotations(me)).get("parent") or "")
    if not parent:
        return None
    shown = awg.show(parent)
    work = shown.get("work") or {}
    if PLANNED not in ((work.get("execution_policy") or {}).get("capabilities") or []):
        return None
    key = f"plan-{criteria_sha(list(work.get('acceptance_criteria') or []))[:12]}"
    children = (annotation_data(awg.annotations(parent), key) or {}).get("children") or []
    if not children or any(_state(session, str(ref)) not in FINISHED
                           for ref in children if str(ref) != me):
        return None
    session.verify()
    awg.set_capabilities(parent, with_stage(shown, VERIFY))
    session.log("parent_to_verify", {"parent": parent, "children": children})
    return parent


def _state(session: Session, ref: str) -> str:
    return str((session.awg.show(ref).get("work") or {}).get("state", ""))
