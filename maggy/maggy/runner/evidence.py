"""Commit-bound evidence for each required check, attached once with the ci credential.

Each record is bound to the item's required CI `test` validation (AWG counts evidence toward
a validation only when it names it), carries spec_version and the check name, and is wrapped
in intent/result annotations keyed `<ref>:<attempt>:evidence:<check>:<sha>`, so a
roll-forward after a crash skips what was already attached (RFC §2.4, §2.6.1).
"""

from __future__ import annotations

from maggy.runner.awg_types import EvidenceSpec, annotation_key
from maggy.runner.session import Session
from maggy.worker.models import CheckResult, WorkerResult


def attach_evidence(session: Session, result: WorkerResult) -> None:
    shown = session.awg.show(session.claim.ref)
    validation = ci_validation(shown)
    recorded = {annotation_key(note) for note in session.awg.annotations(session.claim.ref)}
    for check in result.checks:
        key = f"{session.claim.ref}:{session.claim.attempt_id}:evidence:{check.name}:{check.sha}"
        if f"{key}:result" not in recorded:
            _attach(session, check, (key, validation))


def ci_validation(shown: dict) -> str | None:
    """The id of the item's first required `test` validation, if it has one."""
    found = [v for v in shown.get("validations") or []
             if v.get("kind") == "test" and v.get("required", True)]
    return str(found[0]["id"]) if found else None


def _attach(session: Session, check: CheckResult, target: tuple[str, str | None]) -> None:
    key, validation = target
    claim = session.claim
    session.verify()
    marker = {"action": "evidence", "check": check.name, "sha": check.sha}
    session.awg.annotate(claim, key, {"phase": "intent", **marker})
    meta = {"spec_version": str(claim.version), "check": check.name}
    spec = EvidenceSpec(kind=check.name, verdict="PASS" if check.passed else "FAIL",
                        commit_sha=check.sha, validation=validation, meta=meta)
    record = session.awg.evidence(claim, spec)
    session.awg.annotate(claim, f"{key}:result", {"phase": "result", **marker,
                                                  "id": record.get("id")})
    session.log("evidence", {"check": check.name, "passed": check.passed, "sha": check.sha,
                             "validation": validation})
