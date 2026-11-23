"""Managed tables/keys in TOML files, via tomlkit to keep comments and layout."""

from __future__ import annotations

from typing import Any

import tomlkit
from tomlkit.exceptions import TOMLKitError

from maggy.harness.region_errors import RegionError
from maggy.harness.region_keys import REMOVE, changed_paths, extract_keys, get_path, parent_of


def _load(content: str | None) -> tomlkit.TOMLDocument:
    try:
        return tomlkit.parse(content or "")
    except TOMLKitError as exc:
        raise RegionError(f"invalid TOML ({exc}); file left untouched") from exc


def _super_table() -> Any:
    return tomlkit.table(is_super_table=True)


def render_toml(content: str | None, regions: dict[str, Any]) -> str:
    doc = _load(content)
    changed = changed_paths(doc, regions)
    if content is not None and not changed:
        return content
    for path in changed:
        if regions[path] is REMOVE:
            _remove(doc, path)
            continue
        parent, last = parent_of(doc, path, _super_table)
        parent[last] = regions[path]
    return tomlkit.dumps(doc)


def _remove(doc: tomlkit.TOMLDocument, path: str) -> None:
    head, _, last = path.rpartition(".")
    parent = get_path(doc, head) if head else doc
    del parent[last]


def extract_toml(content: str | None, ids: list[str]) -> dict[str, str | None]:
    return extract_keys(_load(content), ids)
