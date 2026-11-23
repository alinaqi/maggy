"""Reject credential-looking keys: secrets never belong in a harness profile."""

from __future__ import annotations

import re
from typing import Any

_SECRET_WORDS = frozenset({
    "token", "secret", "secrets", "password", "passwords", "passwd",
    "apikey", "credential", "credentials",
})
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def is_secret_key(key: str) -> bool:
    """True when a key name looks like it holds a credential."""
    words = re.split(r"[_\-.\s]+", _CAMEL.sub("_", key).lower())
    joined = {a + b for a, b in zip(words, words[1:])}
    return bool(_SECRET_WORDS & (set(words) | joined))


def find_secret_keys(data: Any, path: str = "") -> list[str]:
    """Key paths (a.b[0].c) of every credential-looking key, at any depth."""
    if isinstance(data, list):
        return [hit for i, item in enumerate(data)
                for hit in find_secret_keys(item, f"{path}[{i}]")]
    if not isinstance(data, dict):
        return []
    found: list[str] = []
    for key, value in data.items():
        child = f"{path}.{key}" if path else str(key)
        if is_secret_key(str(key)):
            found.append(child)
        found.extend(find_secret_keys(value, child))
    return found
