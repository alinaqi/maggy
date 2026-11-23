"""Protected paths: edits here send the candidate to a human (RFC §2.6.5)."""

from __future__ import annotations

from fnmatch import fnmatchcase

from maggy.harness.schema import HarnessProfile
from maggy.worker.models import Blocker

ALWAYS_PROTECTED = (".github/**", ".maggy/**")


def protected_patterns(profile: HarnessProfile) -> list[str]:
    high = profile.risk.high.paths if profile.risk.high else []
    return [*ALWAYS_PROTECTED, *high]


def protected_paths(changed: list[str], profile: HarnessProfile) -> list[str]:
    """Changed files matching risk.high paths, CI config or locked policy files."""
    patterns = protected_patterns(profile)
    return [path for path in changed if any(fnmatchcase(path, pat) for pat in patterns)]


def protected_blocker(hits: list[str]) -> Blocker | None:
    if not hits:
        return None
    return Blocker(question=("The agent changed protected path(s): " + ", ".join(hits)
                             + ". Move to WAITING_HUMAN: approve these edits before advancing?"),
                   options=["approve", "reject"])
