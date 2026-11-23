"""The spec stage (RFC §2.4, §2.5) for items claimed with `stage:spec`.

A read-only author drafts structured criteria (SpecDraft); a reviewer in a fresh session,
on `agents.prefer.review` when set, judges it (SpecReview). Malformed output gets one retry
with the validation error, then the stage fails before any graph mutation. The verdict is
applied by `spec_gate`.
"""

from __future__ import annotations

from maggy.runner.attempt import workspace_for
from maggy.runner.session import RunReport, Session
from maggy.runner.stages.models import SpecDraft, SpecReview
from maggy.runner.stages.spec_gate import apply_verdict
from maggy.runner.stages.spec_prompt import SpecContext, author_prompt, review_prompt
from maggy.runner.stages.structured import ask_structured
from maggy.runner.stages.worker import StageWorkers
from maggy.runner.workspace import prepare_workspace


def run_spec(session: Session, shown: dict) -> RunReport:
    session.verify()
    workspace = workspace_for(session)
    base = prepare_workspace(session.config.repo, workspace, session.claim.ref)
    workers = StageWorkers(session, "spec", (workspace, base))
    ctx = SpecContext(session.claim, shown, session.config.repo)
    draft = ask_structured(lambda p: workers.ask("author", p), author_prompt(ctx), SpecDraft)
    session.log("spec_drafted", {"criteria": len(draft.acceptance_criteria)})
    review = ask_structured(lambda p: workers.ask("review", p), review_prompt(ctx, draft),
                            SpecReview)
    session.log("spec_reviewed", {"verdict": review.verdict})
    return apply_verdict(session, (shown, draft, review))
