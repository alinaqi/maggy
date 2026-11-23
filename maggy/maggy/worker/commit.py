"""The runner (not the agent) commits the attempt's changes (RFC §2.6.2)."""

from __future__ import annotations

from dataclasses import dataclass, field

from maggy.worker.git_ops import run_git
from maggy.worker.models import WorkerSpec

MAGGY_NAME = "Maggy"
MAGGY_EMAIL = "maggy@localhost"
IDENTITY = {"GIT_AUTHOR_NAME": MAGGY_NAME, "GIT_AUTHOR_EMAIL": MAGGY_EMAIL,
            "GIT_COMMITTER_NAME": MAGGY_NAME, "GIT_COMMITTER_EMAIL": MAGGY_EMAIL}


@dataclass(frozen=True)
class Candidate:
    """The candidate commit (None when nothing changed) and files changed since base."""

    commit: str | None
    changed_files: list[str] = field(default_factory=list)


def commit_message(spec: WorkerSpec) -> str:
    return (f"maggy: {spec.awg_ref} attempt {spec.attempt_id}\n\n"
            f"AWG-Ref: {spec.awg_ref}\nAttempt-Id: {spec.attempt_id}\n")


def commit_candidate(spec: WorkerSpec) -> Candidate:
    """Stage everything (incl. untracked, non-ignored), commit as Maggy, diff against base."""
    workspace = spec.workspace
    run_git(workspace, ["add", "-A"])
    if run_git(workspace, ["status", "--porcelain", "--untracked-files=no"]):
        run_git(workspace, ["commit", "-q", "--no-verify", "-m", commit_message(spec)],
                IDENTITY)
    head = run_git(workspace, ["rev-parse", "HEAD"])
    if head == run_git(workspace, ["rev-parse", spec.base_commit]):
        return Candidate(None)
    diff = ["diff", "--name-only", "--no-renames", f"{spec.base_commit}..{head}"]
    names = run_git(workspace, diff)
    return Candidate(head, sorted(names.splitlines()))
