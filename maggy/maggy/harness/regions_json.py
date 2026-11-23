"""Managed keys in JSON files: merge without touching other keys or order.

JSONC (comments) is not supported: such files are reported, never rewritten.
"""

from __future__ import annotations

import json
import re
from typing import Any

from maggy.harness.region_errors import RegionError
from maggy.harness.region_keys import changed_paths, extract_keys, parent_of


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
    for path in changed:
        parent, last = parent_of(data, path, dict)
        parent[last] = regions[path]
    text = json.dumps(data, indent=_indent_of(content), ensure_ascii=False)
    return text + "\n" if content is None or content.endswith("\n") else text


def extract_json(content: str | None, ids: list[str]) -> dict[str, str | None]:
    return extract_keys(_load(content), ids)
