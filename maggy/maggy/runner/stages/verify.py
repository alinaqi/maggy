"""The verify stage (RFC §2.5 Verify) for items claimed with `stage:verify`.

Design choice: verify is the PARENT item's step, not an extra child. The plan stage parks
the parent with its children recorded in the `plan-<criteria sha>` annotation; when the
parent is tagged `stage:verify` it is verified once every build child is finished (DONE or
VERIFYING). The integrated candidate is maggy/<parent ref> with each child's maggy/<child>
branch merged in, plus any human-approved baselines, committed by the runner (§2.6.5:
maggy/* only, compare-and-swap). Checks run in fresh worktrees at that SHA (§2.6.2); the
test plan is the union of the children's `task-plan` annotations.
"""

from __future__ import annotations

from maggy.runner.awg_types import annotation_data
from maggy.runner.prompt import task_plan_of
from maggy.runner.session import RunReport, Session
from maggy.runner.stages.plan_gate import back_to_spec
from maggy.runner.stages.spec_version import SPEC_APPROVED, criteria_sha, latest, spec_is_current
from maggy.runner.stages.verify_gate import conclude_verify
from maggy.runner.verify.baselines import approved_files
from maggy.runner.verify.branch import commit_files, integrate
from maggy.runner.verify.run import run_all

FINISHED = ("DONE", "VERIFYING")


def run_verify(session: Session, shown: dict) -> RunReport:
    session.verify()
    claim, awg = session.claim, session.awg
    if not spec_is_current(latest(awg.decisions(claim.ref), SPEC_APPROVED),
                           claim.acceptance_criteria):
        return back_to_spec(session, shown)
    children = planned_children(session)
    waiting = [ref for ref in children
               if (awg.show(ref).get("work") or {}).get("state") not in FINISHED]
    if waiting:
        return session.give_back("waiting_children",
                                 f"build children not finished: {', '.join(waiting)}")
    sha = candidate(session, children)
    session.log("verify_candidate", {"sha": sha, "children": children})
    entries = [e for ref in children
               for e in task_plan_of(awg.annotations(ref)).get("test_plan") or []]
    return conclude_verify(session, run_all(session, sha, entries))


def planned_children(session: Session) -> list[str]:
    key = f"plan-{criteria_sha(session.claim.acceptance_criteria)[:12]}"
    record = annotation_data(session.awg.annotations(session.claim.ref), key) or {}
    return [str(ref) for ref in record.get("children") or []]


def candidate(session: Session, children: list[str]) -> str:
    """The integrated branch head, with intact human-approved baselines committed."""
    repo, ref = session.config.repo, session.claim.ref
    session.verify()
    sha = integrate(repo, ref, children)
    approved = approved_files(session.awg.annotations(ref), session.awg.decisions(ref))
    if approved:
        session.verify()
        sha = commit_files(repo, ref, approved)
        session.log("baselines_committed", {"sha": sha, "files": sorted(approved)})
    return sha
