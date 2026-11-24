"""Build conclude step: prove each planned regression test of the item, attach the per-
criterion evidence, and fail the attempt back to build with the trace when any is unproven.

The test plan comes from the item's `task-plan` annotation (made by the plan stage); items
without one are untouched. Base is the merge-base of the repo HEAD and the candidate (the
commit the attempt branched from), so a crash roll-forward proves the same pair.
"""

from __future__ import annotations

from maggy.runner.awg_types import EvidenceSpec
from maggy.runner.evidence import attach_once, recorded_keys
from maggy.runner.prompt import task_plan_of
from maggy.runner.regression.prove import Proof, ProofPlan, prove
from maggy.runner.session import Session
from maggy.worker.git_ops import run_git
from maggy.worker.models import WorkerResult

MAX_HANDOFF = 3000


def prove_regressions(session: Session, result: WorkerResult) -> str | None:
    """None when every planned regression test is proven (or none is planned), else why."""
    entries = planned_tests(session)
    if not entries or result.candidate_commit is None:
        return None
    plan = _plan(session, result.candidate_commit)
    proofs = []
    for entry in entries:
        session.verify()  # keeps the lease alive between (possibly slow) test runs
        proofs.append(prove(plan, entry))
    attach_proofs(session, proofs, plan.commits)
    session.log("regression", {p.criterion_id: p.outcome for p in proofs})
    return failure_text([p for p in proofs if p.outcome != "proven"])


def planned_tests(session: Session) -> list[dict]:
    plan = task_plan_of(session.awg.annotations(session.claim.ref))
    return [e for e in plan.get("test_plan") or [] if e.get("regression_test_name")]


def attach_proofs(session: Session, proofs: list[Proof], commits: tuple[str, str]) -> None:
    validations = session.awg.show(session.claim.ref).get("validations") or []
    recorded = recorded_keys(session)
    prefix = f"{session.claim.ref}:{session.claim.attempt_id}:evidence:regression"
    for proof in proofs:
        key = f"{prefix}:{proof.criterion_id}:{commits[1]}"
        spec = proof_spec(session, proof, (commits, _validation(validations, proof)))
        attach_once(session, (key, recorded), spec)


def proof_spec(session: Session, proof: Proof,
               context: tuple[tuple[str, str], str | None]) -> EvidenceSpec:
    (base, candidate), validation = context
    meta = {"spec_version": str(session.claim.version), "criterion_id": proof.criterion_id,
            "check": "regression", "base_commit": base, "regression_test": proof.test,
            "result_kind": proof.outcome}
    return EvidenceSpec(kind="test", verdict="PASS" if proof.outcome == "proven" else "FAIL",
                        commit_sha=candidate, validation=validation, meta=meta)


def failure_text(failed: list[Proof]) -> str | None:
    if not failed:
        return None
    lines = [f"[{p.criterion_id}] {p.test}: {p.outcome}: {p.trace}" for p in failed]
    return ("regression proof failed:\n" + "\n".join(lines))[:MAX_HANDOFF]


def _validation(validations: list[dict], proof: Proof) -> str | None:
    """The plan stage's validation for this criterion + test (title `[AC] test: ...`)."""
    title = f"[{proof.criterion_id}] {proof.test}:"
    found = [v for v in validations if str(v.get("title", "")).startswith(title)]
    return str(found[0]["id"]) if found else None


def _plan(session: Session, candidate: str) -> ProofPlan:
    repo = session.config.repo
    base = run_git(repo, ["merge-base", "HEAD", candidate])
    return ProofPlan(repo=repo, commits=(base, candidate),
                     work_dir=session.attempt_dir / "regression", profile=session.config.profile)
