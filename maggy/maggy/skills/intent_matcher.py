"""Match user messages to protocol triggers.

A protocol (run-tests, git-push, create-pr…) is a fast-path shortcut that
short-circuits the agent and just runs canned steps. So it must only fire on a
*bare invocation* ("run tests", "push to github"), never on a compound build
request that merely mentions a trigger as one clause — e.g. "implement it, test
it, then merge it" must reach the agent (which implements AND tests), not run
the test protocol alone.
"""
from __future__ import annotations

import re

from maggy.skills.protocol_models import Protocol

# Verbs/connectors that mean "do real work" or "then do another thing" — their
# presence (OUTSIDE the matched trigger) marks an agent task, not a bare
# protocol invocation. We check this on the message with the trigger removed, so
# a trigger that legitimately contains "create" (create-pr) isn't self-vetoed.
_BUILD_INTENT = re.compile(
    r"\b(implement|build|creat\w*|add|write|fix|refactor|design|develop|"
    r"generate|merge|then|after that|also)\b",
)


def match_protocol(
    message: str, protocols: list[Protocol],
) -> Protocol | None:
    if not protocols:
        return None
    lower = message.lower()
    best: Protocol | None = None
    best_trigger = ""
    for proto in protocols:
        for trigger in proto.triggers:
            tl = trigger.lower()
            if tl in lower and len(tl) > len(best_trigger):
                best = proto
                best_trigger = tl
    if best is None:
        return None
    # Veto when the request carries build/multi-step intent BEYOND the trigger
    # itself — then it's an agent task ("implement it, test it, then merge it"),
    # and the agent runs the tests as part of doing the work.
    remainder = lower.replace(best_trigger, " ", 1)
    if _BUILD_INTENT.search(remainder):
        return None
    return best
