"""Text output for diff/apply: unified diffs, problems and the conflict hint."""

from __future__ import annotations

import difflib

from maggy.harness.changes import FileChange

HINT = ("resolve conflicts with --take-mine (keep your edits as the new managed text) "
        "or --take-profile (overwrite them with the profile)")


def pending(changes: list[FileChange]) -> list[FileChange]:
    return [c for c in changes if c.status == "ok" and c.kind != "unchanged"]


def problems(changes: list[FileChange]) -> list[FileChange]:
    return [c for c in changes if c.status != "ok"]


def unified(change: FileChange) -> str:
    """Unified diff of one change; /dev/null stands for a missing side."""
    old = "/dev/null" if change.before is None else str(change.path)
    new = "/dev/null" if change.after is None else str(change.path)
    lines = difflib.unified_diff((change.before or "").splitlines(), (change.after or "").splitlines(),
                                 fromfile=old, tofile=new, lineterm="")
    return "\n".join(lines)


def problem_text(change: FileChange) -> str:
    head = f"{change.status}: {change.path}: {change.reason}"
    return f"{head}\n{change.diff3}" if change.diff3 else head


def report_lines(changes: list[FileChange]) -> list[str]:
    """Every pending diff, then every problem, then the hint if there are conflicts."""
    out = [unified(c) for c in pending(changes)]
    out += [problem_text(c) for c in problems(changes)]
    if any(c.status == "conflict" for c in changes):
        out.append(HINT)
    return out
