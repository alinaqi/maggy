"""After the worker: fence, spec version, commit-bound evidence, then block/give back/submit.

Every side effect is preceded by `session.verify()` (STOP + live fence). Evidence goes
through the ci credential, bound to the candidate SHA, with spec_version and check name
(`runner.evidence`).
"""

from __future__ import annotations

from maggy.runner.evidence import attach_evidence
from maggy.runner.session import RunReport, Session
from maggy.worker.models import WorkerResult


def conclude(session: Session, result: WorkerResult) -> RunReport:
    session.verify()
    drift = _spec_drift(session)
    if drift:
        return session.give_back("spec_review", drift)
    attach_evidence(session, result)
    if result.blocker is not None:
        return _block(session, result.blocker.question)
    problem = _not_ready(result)
    if problem:
        return session.give_back("failed", problem)
    return _publish(session, result)


def _spec_drift(session: Session) -> str | None:
    claimed = session.claim.version
    current = int((session.awg.show(session.claim.ref).get("work") or {}).get("version", claimed))
    if current == claimed:
        return None
    return (f"spec version changed from {claimed} to {current} during the run; "
            "returned for spec review")


def _block(session: Session, question: str) -> RunReport:
    session.verify()
    session.awg.block(session.claim, question, human=True)
    session.log("blocked", {"question": question})
    return session.report("waiting_human", question)


def _not_ready(result: WorkerResult) -> str | None:
    if result.outcome != "succeeded":
        return f"worker {result.outcome}"
    if result.candidate_commit is None:
        return "the worker changed nothing"
    failed = [check.name for check in result.checks if not check.passed]
    return f"required checks failed: {', '.join(failed)}" if failed else None


def _publish(session: Session, result: WorkerResult) -> RunReport:
    sha = result.candidate_commit or ""
    if session.config.pr_step is not None:
        session.verify()
        session.config.pr_step(session.claim, result)
        session.log("pr_step", {"sha": sha})
    session.verify()
    session.awg.submit(session.claim, f"maggy: candidate {sha[:12]} passed required checks", sha)
    session.log("submitted", {"sha": sha})
    return session.report("submitted", sha)
