"""Run every verify check on the candidate: repo commands, each criterion's functional or
visual check, then the vision reviewer on each visual capture that matched its baseline."""

from __future__ import annotations

from dataclasses import dataclass, field

from maggy.runner.session import Session
from maggy.runner.stages.spec_version import criterion_ids
from maggy.runner.verify.functional import FUNCTIONAL, run_functional, run_repo_commands
from maggy.runner.verify.models import ViewResult, VisualJob
from maggy.runner.verify.ollama_vision import OllamaVision
from maggy.runner.verify.vision import VisionRequest, review_criterion
from maggy.runner.verify.visual import check_visual
from maggy.worker.models import CheckResult

VISION_REVIEWED = "vision-reviewed"  # a human's review: DECISION key :<criterion>:<viewport>


@dataclass
class VerifyOutcome:
    sha: str
    commands: list[CheckResult] = field(default_factory=list)
    results: list[ViewResult] = field(default_factory=list)
    entries: list[dict] = field(default_factory=list)  # the test plan the checks ran from


def run_all(session: Session, sha: str, entries: list[dict]) -> VerifyOutcome:
    job = VisualJob(session.config.repo, sha, session.attempt_dir / "verify",
                    session.config.profile)
    outcome = VerifyOutcome(sha, run_repo_commands(job), entries=list(entries))
    for entry in entries:
        session.verify()  # keeps the lease alive between (possibly slow) checks
        outcome.results += _check(job, entry)
    reviewed = [_vision(session, sha, result) for result in outcome.results
                if result.check == "visual" and result.verdict == "PASS"
                and "expected" in result.artifacts]
    outcome.results += reviewed
    return outcome


def _check(job: VisualJob, entry: dict) -> list[ViewResult]:
    if entry.get("evidence") in FUNCTIONAL:
        return [run_functional(job, entry)]
    if entry.get("evidence") == "visual":
        return check_visual(job, entry)
    return []  # manual acceptance is the PR reviewer's, not an automated check


def _vision(session: Session, sha: str, result: ViewResult) -> ViewResult:
    """The vision reviewer's verdict (or a human's `vision-reviewed` DECISION at this sha)."""
    cid, viewport = result.criterion_id, result.viewport
    if _human_reviewed(session, sha, (cid, viewport)):
        return ViewResult(cid, viewport, "PASS", "reviewed by a human", check="vision")
    texts = criterion_ids(session.claim.acceptance_criteria)
    request = VisionRequest(cid, texts.get(cid, ""), result.artifacts["expected"],
                            result.artifacts["actual"], viewport)
    backends = session.config.vision
    if backends is None:
        backends = [OllamaVision()]
    reviewed = review_criterion(backends, session.config.profile, request)
    return ViewResult(cid, viewport, reviewed.verdict, reviewed.detail, check="vision")


def _human_reviewed(session: Session, sha: str, where: tuple[str, str]) -> bool:
    key = f"{VISION_REVIEWED}:{where[0]}:{where[1]}"
    found = [d for d in session.awg.decisions(session.claim.ref) if d.get("key") == key]
    return bool(found) and (found[-1].get("data") or {}).get("sha") == sha
