"""Blueprint extraction — fingerprint tasks, extract patterns."""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maggy.blueprint_store import BlueprintStore

NOISE_WORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were",
    "in", "on", "at", "for", "to", "of", "and", "or",
    "this", "that", "it", "its", "with", "from", "by",
    "please", "can", "you", "i", "my", "me", "we",
    "do", "did", "does", "be", "been", "have", "has",
    "will", "would", "could", "should", "not", "but",
})

_PATH_RE = re.compile(r"(?:/[\w.\-]+){2,}")
_QUOTED_RE = re.compile(r'"[^"]{2,}"')


def extract_keywords(message: str) -> list[str]:
    """Extract meaningful sorted keywords from message."""
    cleaned = _PATH_RE.sub("", message)
    words = re.findall(r"[a-zA-Z_]+", cleaned.lower())
    filtered = [
        w for w in words
        if len(w) >= 3 and w not in NOISE_WORDS
    ]
    return sorted(set(filtered))


def fingerprint(task_type: str, keywords: list[str]) -> str:
    """Deterministic hash from task type + sorted keywords."""
    key = f"{task_type}:{','.join(sorted(keywords))}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def extract_template(message: str) -> str:
    """Replace specific paths and quoted values with slots."""
    result = _PATH_RE.sub("{path}", message)
    result = _QUOTED_RE.sub("{value}", result)
    return result


def capture_blueprint(
    message: str, task_type: str,
    tool_events: list[str], model: str,
    store: BlueprintStore,
    project_key: str = "",
) -> None:
    """Extract and store blueprint from completed task."""
    keywords = extract_keywords(message)
    if len(keywords) < 2:
        return
    fp = fingerprint(task_type, keywords)
    template = extract_template(message)
    store.record(
        fp, task_type, tool_events,
        keywords, template, model, project_key,
    )


def build_context(bp: dict) -> str:
    """Format blueprint as context for cheaper model."""
    lines = [f"Task type: {bp.get('task_type', '?')}"]
    lines.append("Steps:")
    for i, step in enumerate(bp.get("tool_sequence", []), 1):
        lines.append(f"  {i}. {step}")
    tmpl = bp.get("prompt_template", "")
    if tmpl:
        lines.append(f"Pattern: {tmpl}")
    return "\n".join(lines)
