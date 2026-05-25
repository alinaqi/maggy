"""ChatManager — interactive Claude Code sessions with message queue."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import uuid
from pathlib import Path
from typing import AsyncGenerator

from maggy.config import MaggyConfig
from maggy.services.chat_models import (
    ChatMessage,
    ChatSession,
    enqueue_msg,
)
from maggy.services.chat_media import (
    detect_document,
    detect_image,
    stream_doc,
    stream_vision,
)
from maggy.services.chat_stream import stream_message

logger = logging.getLogger(__name__)

# Re-export for backwards compatibility
__all__ = ["ChatManager", "ChatMessage", "ChatSession", "enqueue_msg"]


def _git_branch(path: str) -> str:
    """Get current git branch for a directory."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=path, capture_output=True, text=True,
            timeout=5,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""


class ChatManager:
    """Manages interactive Claude Code sessions."""

    def __init__(self, cfg: MaggyConfig, store=None):
        self.cfg = cfg
        self._sessions: dict[str, ChatSession] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._store = store
        if store:
            self._restore_sessions(store)

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
        sid = uuid.uuid4().hex[:10]
        branch = _git_branch(wd)
        session = ChatSession(
            id=sid, claude_session_id="",
            project_key=key, working_dir=wd,
            repo_dir=wd, isolation="none",
            label=branch,
        )
        self._sessions[session.id] = session
        self._locks[session.id] = asyncio.Lock()
        if self._store:
            self._store.save_session(
                session.id, key, wd, "",
                repo_dir=wd, isolation="none",
                label=branch,
            )
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

    def rename_session(self, session_id: str, label: str) -> bool:
        """Set a custom label on a session."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.label = label
        if self._store:
            self._store.update_label(session_id, label)
        return True

    def delete_session(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if session:
            del self._sessions[session_id]
            self._locks.pop(session_id, None)
            if self._store:
                self._store.delete_session(session_id)
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
            img = detect_image(message)
            doc = detect_document(message) if not img else None
            if img:
                async for chunk in stream_vision(*img):
                    yield chunk
            elif doc:
                async for chunk in stream_doc(*doc, session):
                    yield chunk
            else:
                async for chunk in stream_message(session, message):
                    yield chunk
                async for chunk in self._drain_queue(session):
                    yield chunk
            self._persist_after_send(session)

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

    def _persist_after_send(self, session: ChatSession) -> None:
        """Save new messages and claude_session_id after send."""
        if not self._store:
            return
        store = self._store
        store.update_claude_id(
            session.id, session.claude_session_id,
        )
        marker = getattr(session, "_persisted_idx", 0)
        new_msgs = session.messages[marker:]
        for msg in new_msgs:
            store.append_message(
                session.id, msg.role, msg.content,
            )
        session._persisted_idx = len(session.messages)

    def _restore_sessions(self, store) -> None:
        """Load persisted sessions from store."""
        for row in store.load_sessions():
            sid = row["id"]
            session = ChatSession(
                id=sid, project_key=row["project_key"],
                claude_session_id=row.get("claude_session_id", ""),
                working_dir=row["working_dir"],
                repo_dir=row.get("repo_dir", ""),
                isolation=row.get("isolation", "none"),
                label=row.get("label", ""),
            )
            for m in store.load_messages(sid):
                session.messages.append(ChatMessage(
                    role=m["role"], content=m["content"],
                    timestamp=m.get("timestamp", ""),
                ))
            session._persisted_idx = len(session.messages)
            self._sessions[sid] = session
