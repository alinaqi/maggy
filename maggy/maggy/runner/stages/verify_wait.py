"""PENDING verification waits for a human (RFC §2.5; factory doc §5): each proposed
baseline is recorded (`baseline-proposed:*` annotation) and the WAITING_HUMAN question
names its image and the DECISION that approves it; a vision review that could not decide
names the `vision-reviewed` DECISION a human can record instead."""

from __future__ import annotations

from maggy.runner.session import RunReport, Session
from maggy.runner.verify.baselines import approval_command, proposal
from maggy.runner.verify.models import ViewResult
from maggy.runner.verify.run import VISION_REVIEWED


def wait_for_human(session: Session, sha: str, pending: list[ViewResult]) -> RunReport:
    ref = session.claim.ref
    lines = [_line(session, result, sha) for result in pending]
    question = (f"Verification of {sha[:12]} is pending:\n" + "\n".join(lines)
                + f"\nThen move {ref} to READY to re-run verify.")
    session.verify()
    session.awg.block(session.claim, question, human=True)
    session.log("verify_waiting_human", {"sha": sha, "pending": len(pending)})
    return session.report("waiting_human", question)


def _line(session: Session, result: ViewResult, sha: str) -> str:
    head = f"- [{result.criterion_id}] {result.check} {result.viewport}: {result.reason}"
    if "proposed" in result.artifacts:
        key, data = proposal(result)
        session.verify()
        session.awg.annotate(session.claim, key, data)
        return (f"{head}\n  proposed baseline: {data['path']}\n  approve: "
                f"{approval_command(session.claim.ref, data)}")
    if result.check == "vision":
        key = f"{VISION_REVIEWED}:{result.criterion_id}:{result.viewport}"
        return (f"{head}\n  after reviewing it yourself: awg decision {session.claim.ref} "
                f"--key {key} --data '{{\"sha\": \"{sha}\"}}'")
    return head
