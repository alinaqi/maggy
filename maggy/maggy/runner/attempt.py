"""Turn a claim into a worker Attempt in the item's stable worktree (RFC §2.3, §2.4)."""

from __future__ import annotations

from maggy.runner.control import pid_dir
from maggy.runner.prompt import build_prompt
from maggy.runner.session import Session
from maggy.runner.workspace import safe_name
from maggy.worker.models import WorkerSpec
from maggy.worker.pipeline import Attempt


def item_stage(shown: dict) -> str:
    """The item's stage: a `stage:<name>` capability, else attributes.stage, else build."""
    work = shown.get("work") or {}
    caps = (work.get("execution_policy") or {}).get("capabilities") or []
    named = [cap.removeprefix("stage:") for cap in caps if str(cap).startswith("stage:")]
    return named[0] if named else str((work.get("attributes") or {}).get("stage", "build"))


def workspace_for(session: Session):
    return session.config.state_dir / "worktrees" / safe_name(session.claim.ref)


def build_attempt(session: Session, base: str) -> Attempt:
    claim, config = session.claim, session.config
    profile, worker = config.profile, config.profile.worker
    attempt_id = safe_name(claim.attempt_id)
    spec = WorkerSpec(awg_ref=claim.ref, attempt_id=attempt_id,
                      fencing_token=str(claim.fencing_token), stage="build", repo=config.repo,
                      base_commit=base, spec_version=claim.version,
                      workspace=workspace_for(session), permission=worker.permission,
                      deadline_s=worker.timeout_minutes * 60,
                      budget_usd=profile.budget.per_run_usd or 0.0, prompt=build_prompt(claim, session.handoff))
    return Attempt(spec=spec, adapter=config.adapter, profile=profile,
                   state_dir=config.state_dir, interrupt_file=session.attempt_dir / "INTERRUPT",
                   pid_file=pid_dir(config.state_dir) / f"{attempt_id}.pid")
