"""Apply the spec reviewer's verdict to the AWG graph (RFC §2.4).

needs_clarification / blocked: the draft is annotated and the item waits for a human with
the single question (or the reason). ready: the WORK criteria are replaced (bumping the spec
version), one REQUIREMENT node per criterion, a `spec-approved` DECISION with that version,
then the item is re-tagged `stage:plan` and released for the plan stage.
Every side effect is preceded by `session.verify()`.
"""

from __future__ import annotations

from maggy.runner.awg_types import NodeSpec, WorkUpdate
from maggy.runner.session import RunReport, Session
from maggy.runner.stages.models import SpecDraft, SpecReview

NEXT_STAGE = "stage:plan"


def apply_verdict(session: Session, verdict: tuple[dict, SpecDraft, SpecReview]) -> RunReport:
    shown, draft, review = verdict
    if review.verdict == "ready":
        return _approve(session, shown, draft)
    session.verify()
    session.awg.annotate(session.claim, f"spec-draft-{session.claim.attempt_id}",
                         {"draft": draft.model_dump(), "verdict": review.verdict,
                          "question": review.question, "issues": review.issues})
    reason = review.reason() if review.verdict == "needs_clarification" else (
        f"spec blocked: {review.reason()}")
    session.verify()
    session.awg.block(session.claim, reason, human=True)
    session.log("spec_waiting_human", {"verdict": review.verdict, "question": reason})
    return session.report("waiting_human", reason)


def _approve(session: Session, shown: dict, draft: SpecDraft) -> RunReport:
    claim, awg = session.claim, session.awg
    criteria = [f"[{c.id}] {c.text}" for c in draft.acceptance_criteria]
    session.verify()
    spec_version = int(awg.update(claim, WorkUpdate(acceptance_criteria=criteria))["version"])
    for criterion in draft.acceptance_criteria:
        session.verify()
        awg.create_node(claim, NodeSpec(type="REQUIREMENT", title=criterion.text,
                                        data={**criterion.model_dump(), "work": claim.ref}))
    session.verify()
    awg.decision(claim, "spec-approved", {"spec_version": spec_version,
                                          "criteria": [c.id for c in draft.acceptance_criteria]})
    session.verify()
    awg.update(claim, WorkUpdate(capabilities=next_stage_capabilities(shown)))
    session.verify()
    awg.release(claim, f"spec v{spec_version} approved; handed to the plan stage")
    session.log("spec_approved", {"spec_version": spec_version})
    return session.report("spec_approved", f"spec v{spec_version}")


def next_stage_capabilities(shown: dict) -> list[str]:
    """The item's capabilities with its stage tag swapped for `stage:plan` (project kept)."""
    caps = ((shown.get("work") or {}).get("execution_policy") or {}).get("capabilities") or []
    kept = [cap for cap in caps if not str(cap).startswith("stage:")]
    return sorted({*kept, "maggy-runner", NEXT_STAGE})
