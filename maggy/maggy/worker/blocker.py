"""Agent-raised blockers: a `QUESTION:` line in the agent's final text (RFC §2.3 Blocker).

The question is reported as data for a human (WAITING_HUMAN); it never grants the agent
anything. Protected-path blockers take precedence (see pipeline).
"""

from __future__ import annotations

import re

from maggy.worker.models import Blocker

MARKER = "QUESTION:"
BLOCKER_INSTRUCTIONS = (
    "If the task is ambiguous or under-specified, do not guess and do not edit any files. "
    f"Instead reply with one line starting with `{MARKER}` followed by the single precise "
    "question a human must answer before the work can proceed.")
_LINE = re.compile(r"^[\s*_#>`-]*question:[\s*_`]*(?P<question>.*?)\s*$", re.IGNORECASE)


def agent_blocker(final_text: str) -> Blocker | None:
    """The first `QUESTION:` line (markdown emphasis tolerated) as a Blocker, else None."""
    for line in final_text.splitlines():
        found = _LINE.match(line)
        if found and found.group("question"):
            return Blocker(question=found.group("question"))
    return None
