"""Pure layering helpers: deep merge, locked-key split and provenance."""

from __future__ import annotations

from typing import Any

_ABSENT = object()


def join(prefix: str, key: object) -> str:
    return f"{prefix}.{key}" if prefix else str(key)


def is_locked(path: str, locked: list[str]) -> bool:
    """A path is locked when it, or one of its ancestors, is listed."""
    return any(path == key or path.startswith(key + ".") for key in locked)


def deep_merge(base: dict, override: dict) -> dict:
    """Dicts merge recursively; lists and scalars from override replace."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def split_locked(data: dict, locked: list[str], prefix: str = "") -> tuple[dict, dict]:
    """Split a layer into (unlocked part, locked part)."""
    free: dict = {}
    held: dict = {}
    for key, value in data.items():
        sub_free, sub_held = _split_value(value, locked, join(prefix, key))
        if sub_free is not _ABSENT:
            free[key] = sub_free
        if sub_held is not _ABSENT:
            held[key] = sub_held
    return free, held


def _split_value(value: Any, locked: list[str], path: str) -> tuple[Any, Any]:
    if is_locked(path, locked):
        return _ABSENT, value
    if not isinstance(value, dict) or not value:
        return value, _ABSENT
    free, held = split_locked(value, locked, path)
    return (free or _ABSENT), (held or _ABSENT)


def provenance_of(data: dict, source: str, prefix: str = "") -> dict[str, str]:
    """Map every key path a layer sets (nodes and leaves) to its source."""
    found: dict[str, str] = {}
    for key, value in data.items():
        path = join(prefix, key)
        found[path] = source
        if isinstance(value, dict):
            found.update(provenance_of(value, source, path))
    return found


def key_paths(data: dict, prefix: str = "") -> set[str]:
    """Every key path present in a nested dict."""
    return set(provenance_of(data, "", prefix))
