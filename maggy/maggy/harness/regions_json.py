"""Managed keys in JSON files: edited in place (json_edit), so every byte
outside the managed keys is preserved.

JSONC (comments) is not supported: such files are reported, never rewritten.
"""

from __future__ import annotations

import json
import re
from typing import Any

from maggy.harness.region_errors import RegionError
from maggy.harness.json_edit import remove_value, set_value
from maggy.harness.region_keys import REMOVE, changed_paths, extract_keys


def _load(content: str | None) -> dict:
    if content is None:
        return {}
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        if re.search(r"(?m)^\s*//|/\*", content):
            raise RegionError("JSONC with comments is not supported; file skipped") from exc
        raise RegionError(f"invalid JSON ({exc}); file left untouched") from exc
    if not isinstance(data, dict):
        raise RegionError("JSON root is not an object; file left untouched")
    return data


def _indent_of(content: str | None) -> str:
    found = re.search(r"\n([ \t]+)\S", content or "")
    return found.group(1) if found else "  "


def render_json(content: str | None, regions: dict[str, Any]) -> str:
    data = _load(content)
    changed = changed_paths(data, regions)
    if content is not None and not changed:
        return content
    text, unit = ("{}\n" if content is None else content), _indent_of(content)
    for path in changed:
        value = regions[path]
        text = remove_value(text, path) if value is REMOVE else set_value(text, (path, value), unit)
    return text


def extract_json(content: str | None, ids: list[str]) -> dict[str, str | None]:
    return extract_keys(_load(content), ids)
