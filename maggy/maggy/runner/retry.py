"""Attempt cap: an item that keeps failing waits for a human instead of re-running forever.

AWG has no max-attempts, so the runner counts its own consecutive failure handoffs on the
item (`[handoff <attempt>] failed: ...` / `unsupported: ...`), newest first. Interruptions
and stops are not the item's fault and are skipped; any other comment (a human's note, the
cap's own block) ends the run, so a human who unblocks the item resets the count.
"""

from __future__ import annotations

from maggy.runner.session import RunReport, Session

FAILED = ("failed:", "unsupported:")
SKIPPED = ("interrupted:", "stopped:")


def trailing_failures(shown: dict) -> int:
    """Consecutive failure handoffs at the end of the item's comment thread."""
    count = 0
    for comment in reversed(shown.get("comments") or []):
        kind = _handoff_kind(str(comment.get("body", "")))
        if kind.startswith(SKIPPED):
            continue
        if not kind.startswith(FAILED):
            break
        count += 1
    return count


def _handoff_kind(body: str) -> str:
    if not body.startswith("[handoff "):
        return ""
    return body.partition("] ")[2]


def block_after_failures(session: Session, failures: int) -> RunReport:
    """Hand the item to a human: it failed `failures` times in a row."""
    question = (f"maggy: {failures} consecutive attempts failed; look at the handoffs and "
                "the attempt logs, then unblock the item to let the runner retry it.")
    session.verify()
    session.awg.handoff(session.claim, f"retry_cap: {question}")
    session.awg.block(session.claim, question, human=True)
    session.log("retry_cap", {"failures": failures})
    return session.report("waiting_human", question)
