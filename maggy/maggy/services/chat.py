"""ChatManager — interactive Claude Code sessions with message queue."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import AsyncGenerator

from maggy.config import MaggyConfig
from maggy.services.chat_models import (
    ChatMessage,
    ChatSession,
    enqueue_msg,
)
from maggy.services.chat_stream import stream_message

logger = logging.getLogger(__name__)

# Re-export for backwards compatibility
__all__ = ["ChatManager", "ChatMessage", "ChatSession", "enqueue_msg"]


def _detect_image(message: str) -> tuple[str, str] | None:
    """Check if message contains an image file path."""
    from maggy.services.vision import extract_image_path
    return extract_image_path(message)


def _detect_document(message: str) -> tuple[str, str] | None:
    """Check if message contains a document file path."""
    from maggy.services.documents import extract_document_path
    return extract_document_path(message)


async def _stream_vision(
    path: str, prompt: str | None,
) -> AsyncGenerator[dict, None]:
    """Stream vision analysis with Ollama→Claude escalation."""
    from maggy.services.model_escalation import vision_with_escalation
    async for chunk in vision_with_escalation(path, prompt or "Analyze this image."):
        yield chunk


async def _stream_doc(
    path: str, prompt: str | None, session,
) -> AsyncGenerator[dict, None]:
    """Extract document text and forward to Claude."""
    from maggy.services.documents import process_document
    async for chunk in process_document(path, prompt, session):
        yield chunk


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
            wd = self._validate_dir(project_path)
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
            doc = _detect_document(message) if not img else None
            if img:
                async for chunk in _stream_vision(*img):
                    yield chunk
            elif doc:
                async for chunk in _stream_doc(*doc, session):
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

    def find_by_working_dir(self, path: str) -> ChatSession | None:
        """Find existing session by resolved working directory."""
        resolved = str(Path(path).expanduser().resolve())
        for s in self._sessions.values():
            if s.working_dir == resolved:
                return s
        return None

    def _validate_dir(self, path: str) -> str:
        """Validate path is an existing directory."""
        candidate = Path(path).expanduser().resolve()
        if not candidate.is_dir():
            raise ValueError(f"Not a directory: {path!r}")
        return str(candidate)

    def _resolve_project(self, project_key: str) -> str:
        """Map project_key to validated working directory."""
        for cb in self.cfg.codebases:
            if cb.key == project_key:
                path = Path(cb.path).expanduser().resolve()
                return str(path)
        raise ValueError(
            f"Project '{project_key}' not found in codebases"
        )
