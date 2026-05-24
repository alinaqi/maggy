"""Chat interaction learner — extract feedback signals from user messages."""

from __future__ import annotations

import re

CORRECTION_PATTERNS = [
    re.compile(r"^no[,.]?\s+(don'?t|that'?s?\s+not|wrong|incorrect)", re.I),
    re.compile(r"^(stop|quit)\s+(doing|using|adding)", re.I),
    re.compile(r"^(instead|actually)[,.]?\s+\w+", re.I),
    re.compile(r"^(not\s+that|not\s+like\s+that)", re.I),
    re.compile(r"^(don'?t|do\s+not)\s+\w+", re.I),
]

PREFERENCE_PATTERNS = [
    re.compile(r"\bi\s+prefer\b", re.I),
    re.compile(r"\bi\s+always\s+want\b", re.I),
    re.compile(r"\balways\s+use\b", re.I),
    re.compile(r"\bnever\s+use\b", re.I),
    re.compile(r"\bplease\s+don'?t\b", re.I),
    re.compile(r"\bi\s+want\s+you\s+to\b", re.I),
]

POSITIVE_PATTERNS = [
    re.compile(r"^perfect[,.]?\s+", re.I),
    re.compile(r"^exactly[,.]?\s+", re.I),
    re.compile(r"^that'?s?\s+(right|correct|it|exactly)", re.I),
    re.compile(r"^(great|good\s+job|nice|well\s+done)[,.]?\s+", re.I),
    re.compile(r"^yes[,.]?\s+(exactly|perfect|that)", re.I),
]

MIN_MSG_LENGTH = 8


def extract_signals(
    user_msg: str, assistant_msg: str, had_error: bool,
) -> list[dict]:
    msg = user_msg.strip()
    if len(msg) < MIN_MSG_LENGTH:
        return []

    signals: list[dict] = []

    if any(p.search(msg) for p in CORRECTION_PATTERNS):
        signals.append({
            "memory_type": "feedback",
            "content": f"User correction: {msg[:200]}",
            "tags": ["correction", "chat"],
            "confidence": 0.8,
        })

    if any(p.search(msg) for p in PREFERENCE_PATTERNS):
        signals.append({
            "memory_type": "preference",
            "content": f"User preference: {msg[:200]}",
            "tags": ["preference", "chat"],
            "confidence": 0.7,
        })

    if any(p.search(msg) for p in POSITIVE_PATTERNS):
        signals.append({
            "memory_type": "feedback",
            "content": f"User confirmed approach: {msg[:200]}",
            "tags": ["positive", "chat"],
            "confidence": 0.6,
        })

    if had_error:
        signals.append({
            "memory_type": "fact",
            "content": f"Error during response to: {msg[:100]}",
            "tags": ["error-pattern", "chat"],
            "confidence": 1.0,
        })

    return signals[:3]
