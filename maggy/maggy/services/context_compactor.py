"""Context compactor — summarize old messages to fit context window.

When conversation length exceeds 80% of the model's context window,
old messages are summarized into a single system message while keeping
the most recent messages intact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

COMPACT_THRESHOLD = 0.80
CHARS_PER_TOKEN = 4

SummarizerFn = Callable[[str], Awaitable[str]]


@dataclass
class CompactionResult:
    messages: list[dict]
    tokens_saved: int = 0
    summary: str = ""


def estimate_tokens(messages: list[dict]) -> int:
    """Rough token estimate based on char count / 4."""
    total = sum(len(m.get("content", "")) for m in messages)
    return total // CHARS_PER_TOKEN


def should_compact(messages: list[dict], context_window: int) -> bool:
    """Check if messages exceed 80% of context window."""
    tokens = estimate_tokens(messages)
    return tokens > int(context_window * COMPACT_THRESHOLD)


async def compact(
    messages: list[dict],
    keep_recent: int = 6,
    summarizer: SummarizerFn | None = None,
) -> CompactionResult:
    """Summarize old messages, keep recent ones."""
    if len(messages) <= keep_recent:
        return CompactionResult(messages=messages)
    old = messages[:-keep_recent]
    recent = messages[-keep_recent:]
    old_text = _format_for_summary(old)
    old_tokens = estimate_tokens(old)
    try:
        if summarizer is None:
            return CompactionResult(messages=messages)
        summary = await summarizer(old_text)
    except Exception as exc:
        logger.debug("Compaction failed: %s", exc)
        return CompactionResult(messages=messages)
    summary_msg = {"role": "system", "content": summary}
    new_tokens = estimate_tokens([summary_msg])
    return CompactionResult(
        messages=[summary_msg, *recent],
        tokens_saved=max(0, old_tokens - new_tokens),
        summary=summary,
    )


def compact_messages(messages: list, keep_recent: int = 8) -> list:
    """Drop oldest messages to reduce context. Works on ChatMessage objects or dicts."""
    if len(messages) <= keep_recent:
        return messages
    return messages[-keep_recent:]


def _format_for_summary(messages: list[dict]) -> str:
    """Format messages into text for summarization."""
    parts: list[str] = []
    for m in messages:
        role = m.get("role", "unknown")
        content = m.get("content", "")[:500]
        parts.append(f"{role}: {content}")
    return "\n".join(parts)
