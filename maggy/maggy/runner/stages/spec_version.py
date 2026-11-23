"""Which spec a stage works from (RFC §2.4): the `spec-approved` DECISION records the
approved criteria's fingerprint; the item's current criteria must still match it.

AWG bumps the WORK version on every claim and state change, so the approved `spec_version`
alone cannot be compared with the claim's version; the criteria fingerprint can.
"""

from __future__ import annotations

import hashlib
import json
import re

SPEC_APPROVED = "spec-approved"
CRITERION_ID = re.compile(r"^\[([^\]]{1,20})\]\s*(.*)$", re.DOTALL)


def criteria_sha(criteria: list[str]) -> str:
    return hashlib.sha256(json.dumps(list(criteria)).encode()).hexdigest()


def latest(decisions: list[dict], key: str) -> dict | None:
    found = [d for d in decisions if d.get("key") == key]
    return found[-1] if found else None


def spec_is_current(approval: dict | None, criteria: list[str]) -> bool:
    data = (approval or {}).get("data") or {}
    return bool(criteria) and data.get("criteria_sha") == criteria_sha(criteria)


def criterion_ids(criteria: list[str]) -> dict[str, str]:
    """criterion id -> text, from `[AC1] text` lines."""
    matches = [CRITERION_ID.match(line.strip()) for line in criteria]
    return {m.group(1): m.group(2) for m in matches if m}
