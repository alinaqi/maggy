"""ChatManager — interactive Claude Code sessions with message queue."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from maggy.config import MaggyConfig
from maggy.services.chat_stream import stream_message

logger = logging.getLogger(__name__)

MAX_QUEUE = 5


def _detect_image(message: str) -> tuple[str, str] | None:
    """Check if message contains an image file path."""
    from maggy.services.vision import extract_image_path
    return extract_image_path(message)


async def _stream_vision(
    path: str, prompt: str | None,
) -> AsyncGenerator[dict, None]:
    """Stream vision analysis as chat chunks."""
    from maggy.services.vision import async_analyze_image
    async for chunk in async_analyze_image(path, prompt):
        yield chunk


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


class ChatManager:
    """Manages interactive Claude Code sessions."""

    def __init__(self, cfg: MaggyConfig):
        self.cfg = cfg
        self._sessions: dict[str, ChatSession] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def create_session(
        self, project_key: str, project_path: str | None = None,
    ) -> ChatSession:
        """Create a new chat session for a project."""
        if project_path:
            wd = self._validate_path(project_path)
            key = project_key or Path(wd).name
        else:
            wd = self._resolve_project(project_key)
            key = project_key
        session = ChatSession(
            id=uuid.uuid4().hex[:10],
            claude_session_id="",
            project_key=key,
            working_dir=wd,
        )
        self._sessions[session.id] = session
        self._locks[session.id] = asyncio.Lock()
        return session

    def find_by_project(self, key: str) -> ChatSession | None:
        """Find existing session for a project key."""
        for s in self._sessions.values():
            if s.project_key == key:
                return s
        return None

    def auto_connect(
        self, active_sessions: list[dict],
    ) -> list[ChatSession]:
        """Create sessions for all active projects."""
        connected: dict[str, ChatSession] = {}
        for active in active_sessions:
            project = active.get("project", "")
            path = active.get("project_path", "")
            if not project or not path:
                continue
            if project in connected:
                continue
            existing = self.find_by_project(project)
            if existing:
                connected[project] = existing
                continue
            try:
                session = self.create_session(project, path)
            except ValueError:
                continue
            connected[project] = session
        return list(connected.values())

    def get_session(self, sid: str) -> ChatSession | None:
        return self._sessions.get(sid)

    def list_sessions(self) -> list[ChatSession]:
        return list(self._sessions.values())

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._locks.pop(session_id, None)
            return True
        return False

    async def send(
        self, session_id: str, message: str,
    ) -> AsyncGenerator[dict, None]:
        """Send message, yield streamed response chunks."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        lock = self._locks.setdefault(
            session_id, asyncio.Lock(),
        )
        if lock.locked():
            pos = enqueue_msg(session, message)
            if pos < 0:
                yield {"type": "error", "content": "Queue full."}
                return
            yield {"type": "queued", "position": pos}
            return
        async with lock:
            img = _detect_image(message)
            if img:
                async for chunk in _stream_vision(*img):
                    yield chunk
            else:
                async for chunk in stream_message(session, message):
                    yield chunk
                async for chunk in self._drain_queue(session):
                    yield chunk

    async def _drain_queue(
        self, session: ChatSession,
    ) -> AsyncGenerator[dict, None]:
        """Process queued messages after current stream."""
        while session.pending_queue:
            msg = session.pending_queue.popleft()
            yield {
                "type": "queue_next",
                "content": msg[:80],
            }
            async for chunk in stream_message(session, msg):
                yield chunk

    def _validate_path(self, path: str) -> str:
        """Validate path is inside a configured codebase root."""
        candidate = Path(path).expanduser().resolve()
        roots = [
            Path(c.path).expanduser().resolve()
            for c in self.cfg.codebases
        ]
        for root in roots:
            try:
                candidate.relative_to(root)
                return str(candidate)
            except ValueError:
                continue
        raise ValueError(
            f"Path {path!r} is not inside any configured "
            f"codebase. Allowed: {[str(r) for r in roots]}"
        )

    def _resolve_project(self, project_key: str) -> str:
        """Map project_key to validated working directory."""
        for cb in self.cfg.codebases:
            if cb.key == project_key:
                path = Path(cb.path).expanduser().resolve()
                return str(path)
        raise ValueError(
            f"Project '{project_key}' not found in codebases"
        )
