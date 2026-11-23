"""Shared types and tolerant helpers for worker CLI output parsers."""

from __future__ import annotations

import json
import math

from pydantic import BaseModel


class RawRun(BaseModel):
    """What the runner captured from one CLI process."""

    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = 0


class ParsedRun(BaseModel):
    """Normalised result of parsing one CLI run."""

    final_text: str = ""
    cost_usd: float | None = None
    model: str | None = None
    usage: dict[str, int] = {}
    error: str | None = None
    quota_hit: bool = False
    session_ref: str | None = None


def load_object(text: str) -> dict | None:
    """Parse one JSON object; anything else (bad JSON, list, scalar) is None."""
    try:
        value = json.loads(text)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def json_lines(text: str) -> tuple[list[dict], list[str]]:
    """Split JSONL into objects plus one problem per malformed line."""
    loaded = [(n, load_object(line)) for n, line in enumerate(text.splitlines(), start=1)
              if line.strip()]
    events = [event for _, event in loaded if event is not None]
    problems = [f"line {n}: malformed JSON" for n, event in loaded if event is None]
    return events, problems


def as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def text_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) else None


def pick_usage(source: object, mapping: dict[str, str]) -> dict[str, int]:
    """Map a CLI's token counters onto maggy's names, keeping only integers."""
    found = {ours: as_dict(source).get(theirs) for ours, theirs in mapping.items()}
    return {key: int(value) for key, value in found.items()
            if number(value) is not None}


def join_errors(messages: list[str]) -> str | None:
    unique = list(dict.fromkeys(m.strip() for m in messages if m and m.strip()))
    return "; ".join(unique) or None


def quota_hit(patterns: list[str], *texts: str | None) -> bool:
    haystack = "\n".join(t for t in texts if t).lower()
    return any(p and p.lower() in haystack for p in patterns)
