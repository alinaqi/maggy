"""Apply the verify results (RFC §2.4, §2.5, §2.6.9).

Every PASS/FAIL is attached as commit-bound evidence with the ci credential (meta:
spec_version, criterion_id, check, viewport). The `verify-<sha>:<attempt>` annotation
records the per-criterion verdicts and the artifacts the PR may reference: only those that
pass the secret scan. Then: any FAIL gives the item back; any PENDING waits for a human
(proposed baselines + how to approve); all PASS submits the candidate.
"""

from __future__ import annotations

import os
from pathlib import Path

from maggy.runner.awg_types import EvidenceSpec
from maggy.runner.evidence import attach_once, ci_validation, recorded_keys
from maggy.runner.pr_evidence.council import COUNCIL_GAPS, PR_REVIEWED
from maggy.runner.pr_evidence.models import EvidenceRecord, gate
from maggy.runner.session import RunReport, Session
from maggy.runner.stages.verify_evidence import evidence_record, publish_record
from maggy.runner.stages.verify_wait import wait_for_human
from maggy.runner.verify.models import ViewResult
from maggy.runner.verify.run import VerifyOutcome
from maggy.runner.verify.secret_scan import referable, scan_text

RANK = {"PASS": 0, "PENDING": 1, "FAIL": 2}


def conclude_verify(session: Session, outcome: VerifyOutcome) -> RunReport:
    """Evidence, then the PR evidence record (review council included), then the gate:
    failed or blocking findings -> back to build; pending/blocked -> a human; else submit."""
    _attach(session, outcome)
    verdicts, scanned = _record(session, outcome)
    record = evidence_record(session, outcome, scanned)
    publish_record(session, record, outcome)
    if gate(record) == "failed":
        lines = [*map(_line, (r for r in outcome.results if r.verdict == "FAIL")),
                 *(f"repo command {n}: FAIL" for n in record.failed_commands),
                 *_findings(record)]
        return session.give_back("failed", "verify failed:\n" + "\n".join(lines))
    if gate(record) == "waiting":
        pending = [r for r in outcome.results if r.verdict == "PENDING"]
        return wait_for_human(session, outcome.sha, (pending, _notes(record, pending)))
    session.verify()
    session.awg.submit(session.claim, f"maggy: verified {outcome.sha[:12]}: {verdicts}",
                       outcome.sha)
    session.log("verified", {"sha": outcome.sha, "verdicts": verdicts})
    return session.report("submitted", outcome.sha)


def _findings(record: EvidenceRecord) -> list[str]:
    return [f"review: blocking: {f.file}:{f.line or ''} {f.title}" for f in record.findings]


def _notes(record: EvidenceRecord, pending: list[ViewResult]) -> list[str]:
    """Waiting reasons not already named by a pending check: unchecked or manual criteria
    and a review that could not run (with the DECISION a human records after reviewing)."""
    named = {r.criterion_id for r in pending}
    rows = [f"- [{row.criterion_id}] {row.verdict}: {row.detail}" for row in record.rows
            if row.verdict in ("pending", "blocked") and row.criterion_id not in named]
    if not record.council_failed:
        return rows
    gaps = [f"- {gap}" for gap in record.gaps if gap.startswith(COUNCIL_GAPS)]
    return [*rows, *gaps, f"  after reviewing the PR yourself: awg decision {record.ref} "
                          f"--key {PR_REVIEWED} --data '{{\"sha\": \"{record.sha}\"}}'"]


def _line(result: ViewResult) -> str:
    where = f" {result.viewport}" if result.viewport else ""
    return f"[{result.criterion_id}] {result.check}{where}: {result.verdict}: {result.reason}"


def _attach(session: Session, outcome: VerifyOutcome) -> None:
    shown = session.awg.show(session.claim.ref)
    recorded, prefix = recorded_keys(session), f"{session.claim.ref}:{session.claim.attempt_id}"
    version, sha = str(session.claim.version), outcome.sha
    for check in outcome.commands:
        spec = EvidenceSpec(kind="test", verdict="PASS" if check.passed else "FAIL",
                            commit_sha=sha, validation=ci_validation(shown),
                            meta={"spec_version": version, "check": check.name})
        attach_once(session, (f"{prefix}:evidence:verify:{check.name}:{sha}", recorded), spec)
    for result in (r for r in outcome.results if r.verdict != "PENDING"):
        key = f"{prefix}:evidence:verify:{result.criterion_id}:{result.check}:{result.viewport}:{sha}"
        attach_once(session, (key, recorded), _spec(session, result, (shown, sha)))


def _spec(session: Session, result: ViewResult, where: tuple[dict, str]) -> EvidenceSpec:
    shown, sha = where
    meta = {"spec_version": str(session.claim.version), "criterion_id": result.criterion_id,
            "check": result.check, **({"viewport": result.viewport} if result.viewport else {})}
    titled = [v for v in shown.get("validations") or []
              if str(v.get("title", "")).startswith(f"[{result.criterion_id}]")]
    return EvidenceSpec(kind="acceptance" if result.check == "vision" else "test",
                        verdict=result.verdict, commit_sha=sha, meta=meta,
                        validation=str(titled[0]["id"]) if titled else None)


def _record(session: Session, outcome: VerifyOutcome
            ) -> tuple[dict[str, str], tuple[list[Path], dict[Path, list[str]]]]:
    verdicts: dict[str, str] = {}
    for result in outcome.results:
        old = verdicts.get(result.criterion_id, "PASS")
        verdicts[result.criterion_id] = max(old, result.verdict, key=RANK.__getitem__)
    paths = [p for r in outcome.results for p in r.artifacts.values()]
    paths += [c.log_path for c in outcome.commands if c.log_path and c.log_path.is_file()]
    allowed, withheld = referable([p for p in dict.fromkeys(paths) if p.is_file()], os.environ)
    if withheld:
        session.log("secret_scan_withheld", {str(p): f for p, f in withheld.items()})
    session.verify()
    session.awg.annotate(session.claim, f"verify-{outcome.sha}:{session.claim.attempt_id}", {
        "sha": outcome.sha, "verdicts": verdicts, "results": [_row(r) for r in outcome.results],
        "artifacts": [str(p) for p in allowed], "withheld": [str(p) for p in withheld]})
    return verdicts, (allowed, withheld)


def _row(result: ViewResult) -> dict:
    return {"criterion_id": result.criterion_id, "check": result.check,
            "viewport": result.viewport, "verdict": result.verdict,
            "reason": "(withheld: secret scan)" if scan_text(result.reason, os.environ)
            else result.reason[:500]}
