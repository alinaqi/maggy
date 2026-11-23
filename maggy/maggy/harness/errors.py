"""Readable harness profile errors: always the file and the key path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError


class HarnessConfigError(ValueError):
    """A harness profile file is invalid; the message names file and key."""

    def __init__(self, source: Path | str, problems: list[str]) -> None:
        self.source = str(source)
        self.problems = problems
        super().__init__(f"{self.source}: " + f"\n{self.source}: ".join(problems))


def schema_problems(exc: ValidationError, raw: dict) -> list[str]:
    """One 'key.path: message' line per distinct problem."""
    lines = [f"{key_path(raw, err['loc'])}: {err['msg']}" for err in exc.errors()]
    return list(dict.fromkeys(lines))


def key_path(raw: Any, loc: tuple) -> str:
    """Longest prefix of a pydantic loc that exists in the raw data.

    Union validation adds type names (e.g. 'bool') to the loc; those are
    not keys the user wrote, so they are dropped.
    """
    parts: list[str] = []
    node = raw
    for part in loc:
        if not _has(node, part) and parts:
            break
        parts.append(f"[{part}]" if isinstance(part, int) else f".{part}")
        node = node[part] if _has(node, part) else None
    return "".join(parts).lstrip(".") or "<root>"


def _has(node: Any, part: Any) -> bool:
    if isinstance(node, dict):
        return part in node
    return isinstance(node, list) and isinstance(part, int) and part < len(node)
