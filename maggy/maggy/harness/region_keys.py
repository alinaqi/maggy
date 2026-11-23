"""Dotted key paths into JSON objects / TOML documents."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, MutableMapping
from typing import Any

from maggy.harness.region_errors import RegionError

MISSING = object()


def unwrap(value: Any) -> Any:
    """Plain Python value (tomlkit items carry formatting wrappers)."""
    return value.unwrap() if hasattr(value, "unwrap") else value


def get_path(data: Any, path: str) -> Any:
    node = data
    for key in path.split("."):
        if not isinstance(node, Mapping) or key not in node:
            return MISSING
        node = node[key]
    return node


def parent_of(data: MutableMapping, path: str, new_container: Callable[[], Any]):
    """The mapping that holds the last key of `path`, creating parents."""
    *heads, last = path.split(".")
    node = data
    for key in heads:
        if key not in node:
            node[key] = new_container()
        node = node[key]
        if not isinstance(node, MutableMapping):
            raise RegionError(f"{path}: '{key}' exists but is not an object/table")
    return node, last


def canonical(value: Any) -> str:
    """Stable text of a managed value: what is hashed into harness.lock."""
    return json.dumps(unwrap(value), indent=2, sort_keys=True, ensure_ascii=False)


def changed_paths(data: Any, regions: dict[str, Any]) -> list[str]:
    return [p for p, v in regions.items() if unwrap(get_path(data, p)) != v]


def extract_keys(data: Any, ids: list[str]) -> dict[str, str | None]:
    values = {rid: get_path(data, rid) for rid in ids}
    return {rid: None if v is MISSING else canonical(v) for rid, v in values.items()}
