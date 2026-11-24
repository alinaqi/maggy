"""The PR step of the verify stage (RFC §2.5 PR row; factory doc §5 'Publish the evidence').

The runner (never the sandbox) feeds the review council the approved criteria, the test
plan and the candidate diff, builds the per-criterion evidence record, and publishes it in
the draft PR body through the configured PR step. A criterion a human recorded as not
applicable is a `criterion-na:<id>` DECISION.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from maggy.runner.awg_types import annotation_data
from maggy.runner.pr_evidence.build import RecordInputs, build_record
from maggy.runner.pr_evidence.council import (PR_REVIEWED, CouncilOutcome, ReviewRequest,
                                              candidate_diff, run_council)
from maggy.runner.pr_evidence.models import EvidenceRecord
from maggy.runner.pr_evidence.render import render_record
from maggy.runner.pr_evidence.screens import ScreenPolicy, with_screenshots
from maggy.runner.publish_git import default_base
from maggy.runner.session import Session
from maggy.runner.stages.spec_version import criteria_sha
from maggy.runner.verify.run import VerifyOutcome
from maggy.worker.models import WorkerResult

NOT_APPLICABLE = "criterion-na"
Scanned = tuple[list[Path], dict[Path, list[str]]]


def evidence_record(session: Session, outcome: VerifyOutcome, scanned: Scanned) -> EvidenceRecord:
    claim, config = session.claim, session.config
    request = ReviewRequest(claim.ref, str(claim.version), outcome.sha,
                            tuple(claim.acceptance_criteria), tuple(outcome.entries),
                            candidate_diff(config.repo, default_base(config.repo), outcome.sha))
    council = _review(session, request)
    session.log("review_council", {"blocking": len(council.blocking), "gap": council.gap})
    inputs = RecordInputs(claim.ref, str(claim.version), outcome, list(claim.acceptance_criteria),
                          scanned, config.state_dir, _not_applicable(session))
    record = build_record(inputs)
    record = replace(record, findings=council.blocking, council_failed=council.failed,
                     gaps=(*record.gaps, *([council.gap] if council.gap else [])),
                     release_impact=release_impact(session))
    return with_screenshots(record, ScreenPolicy(config.profile, config.uploader,
                                                 config.state_dir))


def _review(session: Session, request: ReviewRequest) -> CouncilOutcome:
    """The council's review; when it could not run, a human's `pr-reviewed` DECISION at
    this sha stands in for it (recorded as a gap, so the PR says who reviewed)."""
    council = run_council(session.config.council, request)
    if not council.failed or not _human_reviewed(session, request.sha):
        return council
    return CouncilOutcome(gap=f"{council.gap}; a human recorded the review "
                              f"({PR_REVIEWED} at {request.sha[:12]})")


def _human_reviewed(session: Session, sha: str) -> bool:
    found = [d for d in session.awg.decisions(session.claim.ref) if d.get("key") == PR_REVIEWED]
    return bool(found) and (found[-1].get("data") or {}).get("sha") == sha


def publish_record(session: Session, record: EvidenceRecord, outcome: VerifyOutcome) -> None:
    """Open or update the draft PR with the evidence record (no PR step: logged only)."""
    body = render_record(record)
    (session.attempt_dir / "pr-evidence.md").parent.mkdir(parents=True, exist_ok=True)
    (session.attempt_dir / "pr-evidence.md").write_text(body)
    step = session.config.pr_step
    if step is None:
        return
    result = WorkerResult(outcome="succeeded", candidate_commit=outcome.sha,
                          checks=outcome.commands, elapsed_s=0.0, agent="maggy-runner",
                          model="-", adapter_version="-")
    session.verify()
    step(session.claim, result, body)
    session.log("pr_step", {"sha": outcome.sha, "stage": "verify"})


def release_impact(session: Session) -> str:
    """From the plan: the high-risk files it touches (approved by a human) or none."""
    claim = session.claim
    key = f"plan-{criteria_sha(claim.acceptance_criteria)[:12]}"
    plan = annotation_data(session.awg.annotations(claim.ref), key) or {}
    risky = [str(path) for path in plan.get("risky") or []]
    tasks = ", ".join(map(str, plan.get("tasks") or [])) or "none recorded"
    if risky:
        return (f"Touches high-risk paths: {', '.join(risky)} "
                f"(plan approval required). Plan tasks: {tasks}. Draft PR only; nothing "
                "merges or deploys automatically.")
    return (f"No high-risk paths in the plan. Plan tasks: {tasks}. Draft PR only; nothing "
            "merges or deploys automatically.")


def _not_applicable(session: Session) -> frozenset[str]:
    prefix = f"{NOT_APPLICABLE}:"
    return frozenset(str(d.get("key", ""))[len(prefix):]
                     for d in session.awg.decisions(session.claim.ref)
                     if str(d.get("key", "")).startswith(prefix))
