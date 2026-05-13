"""Verified context — real git state + live session data."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field


@dataclass
class VerifiedContext:
    """Verified project state from real sources."""

    branch: str = ""
    status_summary: str = ""
    recent_commits: list[str] = field(default_factory=list)
    active_sessions: list[dict] = field(default_factory=list)


def gather_verified(working_dir: str) -> VerifiedContext:
    """Gather verified context from git + sessions."""
    branch = _git_branch(working_dir)
    status = _git_status(working_dir)
    commits = _git_log(working_dir)
    sessions = _detect_sessions(working_dir)
    return VerifiedContext(
        branch=branch,
        status_summary=status,
        recent_commits=commits,
        active_sessions=sessions,
    )


def format_verified(ctx: VerifiedContext) -> str:
    """Format verified context as injection text."""
    parts: list[str] = []
    if ctx.branch:
        parts.append(f"Branch: {ctx.branch}")
    if ctx.status_summary:
        parts.append(f"Status: {ctx.status_summary}")
    if ctx.recent_commits:
        lines = "\n".join(f"  {c}" for c in ctx.recent_commits[:5])
        parts.append(f"Recent commits:\n{lines}")
    if ctx.active_sessions:
        lines = "\n".join(
            f"  - {s.get('provider', '?')}: active"
            for s in ctx.active_sessions
        )
        parts.append(f"Active sessions:\n{lines}")
    if not parts:
        return ""
    return "\n".join(parts)


def _run_git(args: list[str], cwd: str) -> str:
    """Run git command, return stdout or empty."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd, capture_output=True,
            text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return ""


def _git_branch(cwd: str) -> str:
    """Get current git branch."""
    return _run_git(
        ["rev-parse", "--abbrev-ref", "HEAD"], cwd,
    )


def _git_status(cwd: str) -> str:
    """Get short git status summary."""
    out = _run_git(["status", "--porcelain"], cwd)
    if not out:
        return "clean"
    lines = out.splitlines()
    return f"{len(lines)} changed files"


def _git_log(cwd: str) -> list[str]:
    """Get recent commit messages."""
    out = _run_git(
        ["log", "--oneline", "-5", "--no-decorate"], cwd,
    )
    if not out:
        return []
    return out.splitlines()[:5]


def _detect_sessions(cwd: str) -> list[dict]:
    """Detect active CLI sessions for directory."""
    try:
        from maggy.services.session_detect import detect_all
        return detect_all(cwd)
    except Exception:
        return []
