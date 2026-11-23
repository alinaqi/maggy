"""Settle dangling publish intents: an intent annotation with no result (RFC §2.4).

A runner killed between an intent and its result leaves the intent dangling. Recovery looks
the action's outcome up by the stable name (the remote maggy/<ref> branch, the open PR whose
head it is) and records it as the missing `<key>:result`, marked `reconciled`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from maggy.runner.awg_types import Claim
from maggy.runner.publish_git import branch_for, remote_sha

if TYPE_CHECKING:
    from maggy.runner.publish import Publisher


def annotation_key(annotation: dict) -> str:
    return str(annotation.get("key") or annotation.get("idempotency_key") or "")


def settle_intents(publisher: Publisher, claim: Claim) -> list[str]:
    """Record a reconciled result for each of the item's dangling intents; their keys."""
    notes = publisher.awg.annotations(claim.ref)
    keys = {annotation_key(note) for note in notes}
    dangling = [note for note in notes if _dangling(note, keys, claim.ref)]
    for note in dangling:
        data = note.get("data") or {}
        action = str(data.get("action", ""))
        record = {"phase": "result", "action": action, "sha": data.get("sha"),
                  "reconciled": True, **_observe(publisher, claim.ref, action)}
        publisher.awg.annotate(claim, f"{annotation_key(note)}:result", record)
    return [annotation_key(note) for note in dangling]


def _dangling(note: dict, keys: set[str], ref: str) -> bool:
    key = annotation_key(note)
    data = note.get("data") or {}
    intent = data.get("phase") == "intent" and data.get("action") in ("push", "pr")
    return intent and key.startswith(f"{ref}:") and f"{key}:result" not in keys


def _observe(publisher: Publisher, ref: str, action: str) -> dict:
    """What the outside world shows for `action`, found by the stable branch name."""
    branch = branch_for(ref)
    if action == "push":
        return {"remote_sha": remote_sha(publisher.config.repo, branch)}
    if action == "pr":
        found = publisher.gh.find(branch) or {}
        return {"number": found.get("number"), "url": found.get("url")}
    return {}
