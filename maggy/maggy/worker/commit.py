"""The runner (not the agent) commits the attempt's changes (RFC §2.6.2).

The agent can rewrite its worktree's `.git` file (it lives in the writable workspace) to
point at a gitdir whose config it controls. So the runner pins `--git-dir` to the admin
dir recorded in the main repo, refuses a `.git` file that no longer points there, and
never runs external diff drivers or textconv.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from maggy.worker.git_ops import run_git
from maggy.worker.models import WorkerSpec
from maggy.worker.worktree import WorktreeError

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
    pin = pinned_git_args(spec)
    workspace = spec.workspace
    run_git(workspace, [*pin, "add", "-A"])
    if run_git(workspace, [*pin, "status", "--porcelain", "--untracked-files=no"]):
        run_git(workspace, [*pin, "commit", "-q", "--no-verify", "-m", commit_message(spec)],
                IDENTITY)
    head = run_git(workspace, [*pin, "rev-parse", "HEAD"])
    if head == run_git(workspace, [*pin, "rev-parse", spec.base_commit]):
        return Candidate(None)
    diff = ["diff", "--name-only", "--no-renames", "--no-ext-diff", "--no-textconv",
            f"{spec.base_commit}..{head}"]
    return Candidate(head, sorted(run_git(workspace, [*pin, *diff]).splitlines()))


def pinned_git_args(spec: WorkerSpec) -> list[str]:
    """--git-dir/--work-tree for the attempt worktree; WorktreeError if `.git` was changed."""
    admin = _admin_dir(spec)
    dot_git = spec.workspace / ".git"
    text = dot_git.read_text() if dot_git.is_file() and not dot_git.is_symlink() else ""
    pointed = spec.workspace / text.removeprefix("gitdir:").strip() if text else None
    if not text.startswith("gitdir:") or pointed.resolve() != admin.resolve():
        raise WorktreeError(f"{dot_git} no longer points at {admin}; refusing to run git there")
    return ["--git-dir", str(admin), "--work-tree", str(spec.workspace)]


def _admin_dir(spec: WorkerSpec) -> Path:
    """The worktree's admin dir, found from the main repo (outside the agent's reach)."""
    common = Path(run_git(spec.repo, ["rev-parse", "--path-format=absolute",
                                      "--git-common-dir"]))
    workspace = spec.workspace.resolve()
    for admin in sorted((common / "worktrees").glob("*")):
        recorded = admin / "gitdir"
        if recorded.is_file() and (admin / recorded.read_text().strip()).resolve().parent == workspace:
            return admin
    raise WorktreeError(f"{spec.workspace} is not a registered worktree of {spec.repo}")
