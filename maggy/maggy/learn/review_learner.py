"""Review feedback learner — extract signals from code review content."""

from __future__ import annotations

import re

ISSUE_PATTERNS = [
    re.compile(r"\b(bug|vulnerability|security\s+issue|race\s+condition)\b", re.I),
    re.compile(r"\b(missing\s+(check|validation|error\s+handling|input))\b", re.I),
    re.compile(r"\b(incorrect|unsafe|broken)\b", re.I),
]

SUGGESTION_PATTERNS = [
    re.compile(r"\b(should\s+(be|use|have|add|consider))\b", re.I),
    re.compile(r"\b(consider\s+(using|adding|switching|refactoring))\b", re.I),
    re.compile(r"\b(recommend|suggest|better\s+to)\b", re.I),
    re.compile(r"\b(refactor|extract|simplify)\b", re.I),
]


def extract_review_signals(
    review_content: str, model: str, task_type: str,
) -> list[dict]:
    if not review_content:
        return []
    signals: list[dict] = []
    sentences = re.split(r"(?<=[.!?])\s+|\n", review_content)

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 15:
            continue
        if any(p.search(sentence) for p in ISSUE_PATTERNS):
            signals.append({
                "memory_type": "fact",
                "content": f"Review flagged: {sentence[:200]}",
                "tags": ["review", "issue", model],
                "confidence": 0.9,
            })
        elif any(p.search(sentence) for p in SUGGESTION_PATTERNS):
            signals.append({
                "memory_type": "decision",
                "content": f"Review suggestion: {sentence[:200]}",
                "tags": ["review", "suggestion", model],
                "confidence": 0.7,
            })

    return signals[:5]


def learn_from_review(
    engram_store, model: str, content: str,
) -> None:
    from maggy.learn._writer import fire_and_forget_write
    signals = extract_review_signals(content, model, "review")
    if signals:
        fire_and_forget_write(engram_store, "review-feedback", signals)
