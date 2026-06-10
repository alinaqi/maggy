"""Match user messages to protocol triggers."""
from __future__ import annotations

from maggy.skills.protocol_models import Protocol


def match_protocol(
    message: str, protocols: list[Protocol],
) -> Protocol | None:
    if not protocols:
        return None
    lower = message.lower()
    best: Protocol | None = None
    best_len = 0
    for proto in protocols:
        for trigger in proto.triggers:
            tl = trigger.lower()
            if tl in lower and len(tl) > best_len:
                best = proto
                best_len = len(tl)
    return best
