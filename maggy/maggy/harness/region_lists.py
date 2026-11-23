"""List regions ('<key>[]'): Maggy owns some entries of a list it shares with the user.

The region value is Maggy's entries only; harness.lock remembers which entries
Maggy last wrote. So a user entry beside them is never a conflict, entries
Maggy wrote earlier are replaced when the profile changes (a tightened
permission profile drops its broad rules), and removing one of Maggy's
entries on disk is a conflict. An entry the user had before Maggy also emitted
it counts as Maggy's from then on.
"""

from __future__ import annotations

import json
from typing import Any

from maggy.harness.region_keys import REMOVE, canonical
from maggy.harness.regions import extract

SUFFIX = "[]"


def is_list(rid: str) -> bool:
    return rid.endswith(SUFFIX)


def key_of(rid: str) -> str:
    return rid[: -len(SUFFIX)]


def on_disk(fmt: str, content: str | None, rid: str) -> list:
    """The whole list at the region's key ([] when absent or not a list)."""
    text = extract(fmt, content, [key_of(rid)])[key_of(rid)]
    value = json.loads(text) if text is not None else []
    return value if isinstance(value, list) else []


def owned_text(current: list, previous: list) -> str:
    """Region text on disk: Maggy's previously written entries still present."""
    return canonical([x for x in previous if x in current])


def full_list(current: list, previous: list, ours: list) -> Any:
    """User entries (in their order) then Maggy's; REMOVE when nothing is left."""
    user = [x for x in current if x not in previous]
    merged = user + [x for x in ours if x not in user]
    return merged if merged else REMOVE
