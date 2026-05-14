"""Data models for chat sessions."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

MAX_QUEUE = 5


@dataclass
class ChatMessage:
    """A single message in a chat session."""

    role: str  # "user" | "assistant"
    content: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


@dataclass
class ChatSession:
    """An interactive Claude Code session."""

    id: str
    claude_session_id: str
    project_key: str
    working_dir: str
    repo_dir: str = ""
    isolation: str = "none"
    label: str = ""
    messages: list[ChatMessage] = field(default_factory=list)
    status: str = "idle"
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )
    pid: int = 0
    history_context: str = ""
    pending_queue: deque = field(
        default_factory=lambda: deque(maxlen=MAX_QUEUE),
    )


def enqueue_msg(session: ChatSession, message: str) -> int:
    """Append message to session queue. Returns position or -1."""
    if len(session.pending_queue) >= MAX_QUEUE:
        return -1
    session.pending_queue.append(message)
    return len(session.pending_queue)
