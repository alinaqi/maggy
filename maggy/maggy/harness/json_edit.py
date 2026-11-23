"""In-place edits of JSON object members: only the edited bytes change.

The text is never re-serialized; a member's value span is replaced, a new
member is inserted after the last one (or into an empty object), and a removed
member takes its separating comma with it. Input must be valid JSON.
"""

from __future__ import annotations

import json
import re
from json.decoder import scanstring
from typing import Any, NamedTuple

from maggy.harness.region_errors import RegionError

_WS = re.compile(r"[ \t\n\r]*")
_INDENT = re.compile(r"[ \t]*")
_DECODER = json.JSONDecoder()


class Member(NamedTuple):
    key: str
    start: int
    vstart: int
    vend: int


def _skip(text: str, pos: int) -> int:
    return _WS.match(text, pos).end()


def members(text: str, opened: int) -> tuple[list[Member], int]:
    """Members of the object whose '{' is at `opened`, and the index of its '}'."""
    out: list[Member] = []
    pos = _skip(text, opened + 1)
    while text[pos] != "}":
        key, after = scanstring(text, pos + 1)
        vstart = _skip(text, _skip(text, after) + 1)
        vend = _DECODER.raw_decode(text, vstart)[1]
        out.append(Member(key, pos, vstart, vend))
        pos = _skip(text, vend)
        pos = _skip(text, pos + 1) if text[pos] == "," else pos
    return out, pos


def _member(text: str, opened: int, key: str) -> Member | None:
    found = [m for m in members(text, opened)[0] if m.key == key]
    return found[-1] if found else None


def _descend(text: str, keys: list[str]) -> tuple[int, int]:
    """Deepest existing object along keys[:-1]: ('{' index, number of keys walked)."""
    opened = _skip(text, 0)
    for depth, key in enumerate(keys[:-1]):
        found = _member(text, opened, key)
        if found is None:
            return opened, depth
        if text[found.vstart] != "{":
            raise RegionError(f"{'.'.join(keys)}: '{key}' exists but is not an object/table")
        opened = found.vstart
    return opened, len(keys) - 1


def _layout(text: str, pos: int) -> tuple[str, str]:
    """(newline style, indentation of the line holding `pos`)."""
    line = text.rfind("\n", 0, pos) + 1
    return ("\r\n" if "\r\n" in text else "\n"), _INDENT.match(text, line).group(0)


def _dump(value: Any, where: tuple[str, str], unit: str) -> str:
    newline, indent = where
    return json.dumps(value, indent=unit, ensure_ascii=False).replace("\n", newline + indent)


def _insert(text: str, where: tuple[int, str], item: tuple[str, Any]) -> str:
    """Add member `item` to the object at where[0]; where[1] is the indent unit."""
    (opened, unit), (key, value) = where, item
    mems, close = members(text, opened)
    if mems and "\n" not in text[opened:mems[-1].start]:
        entry = f", {json.dumps(key, ensure_ascii=False)}: {json.dumps(value, ensure_ascii=False)}"
        return text[:mems[-1].vend] + entry + text[mems[-1].vend:]
    newline, outer = _layout(text, mems[-1].start if mems else opened)
    inner = outer if mems else outer + unit
    entry = f"{json.dumps(key, ensure_ascii=False)}: {_dump(value, (newline, inner), unit)}"
    if mems:
        return text[:mems[-1].vend] + f",{newline}{inner}{entry}" + text[mems[-1].vend:]
    return text[:opened + 1] + f"{newline}{inner}{entry}{newline}{outer}" + text[close:]


def set_value(text: str, item: tuple[str, Any], unit: str) -> str:
    """Set dotted path item[0] to item[1], creating missing parent objects."""
    path, value = item
    keys = path.split(".")
    opened, depth = _descend(text, keys)
    found = _member(text, opened, keys[-1]) if depth == len(keys) - 1 else None
    if found is not None:
        return text[:found.vstart] + _dump(value, _layout(text, found.start), unit) + text[found.vend:]
    for key in reversed(keys[depth + 1:]):
        value = {key: value}
    return _insert(text, (opened, unit), (keys[depth], value))


def remove_value(text: str, path: str) -> str:
    keys = path.split(".")
    opened, depth = _descend(text, keys)
    found = _member(text, opened, keys[-1]) if depth == len(keys) - 1 else None
    if found is None:
        return text
    mems, close = members(text, opened)
    i = mems.index(found)
    if i > 0:
        return text[:mems[i - 1].vend] + text[found.vend:]
    if len(mems) > 1:
        return text[:found.start] + text[mems[1].start:]
    return text[:opened + 1] + text[close:]
