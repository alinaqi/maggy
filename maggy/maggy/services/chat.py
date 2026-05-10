"""ChatManager — interactive Claude Code sessions from the web UI.

Spawns `claude -p` with --output-format stream-json and uses --resume
for conversation continuity. Auto-connects to active projects and
injects session history for context awareness.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

from maggy.config import MaggyConfig

logger = logging.getLogger(__name__)

CLAUDE_BIN = "claude"


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
    status: str = "idle"  # "idle" | "streaming" | "error"
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )
    pid: int = 0
    history_context: str = ""


class ChatManager:
    """Manages interactive Claude Code sessions."""

    def __init__(self, cfg: MaggyConfig):
        self.cfg = cfg
        self._sessions: dict[str, ChatSession] = {}

    def create_session(
        self, project_key: str, project_path: str | None = None,
    ) -> ChatSession:
        """Create a new chat session for a project."""
        if project_path:
            wd = str(Path(project_path).expanduser().resolve())
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
        return session

    def find_by_project(self, project_key: str) -> ChatSession | None:
        """Find existing session for a project key."""
        for s in self._sessions.values():
            if s.project_key == project_key:
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
            session = self.create_session(project, path)
            connected[project] = session
        return list(connected.values())

    def get_session(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[ChatSession]:
        return list(self._sessions.values())

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    async def send(
        self, session_id: str, message: str,
    ) -> AsyncGenerator[dict, None]:
        """Send message, yield streamed response chunks."""
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        session.messages.append(
            ChatMessage(role="user", content=message)
        )
        session.status = "streaming"
        cmd = self._build_cmd(session, message)
        response_text = ""
        try:
            import os
            env = {
                k: v for k, v in os.environ.items()
                if k != "CLAUDECODE"
            }
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=session.working_dir,
                env=env,
            )
            session.pid = proc.pid or 0
            async for line in proc.stdout:
                text = line.decode(
                    "utf-8", errors="replace"
                ).strip()
                if not text:
                    continue
                chunk = self._parse_chunk(text, session)
                if chunk:
                    response_text += chunk.get("content", "")
                    yield chunk
            await proc.wait()
            session.status = "idle"
        except FileNotFoundError:
            session.status = "error"
            yield {
                "type": "error",
                "content": "claude CLI not found on PATH",
            }
        except Exception as e:
            session.status = "error"
            yield {"type": "error", "content": str(e)}
        if response_text:
            session.messages.append(
                ChatMessage(
                    role="assistant", content=response_text,
                )
            )

    def _build_cmd(
        self, session: ChatSession, message: str,
    ) -> list[str]:
        """Build claude CLI command."""
        cmd = [
            CLAUDE_BIN, "-p", message,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]
        if session.claude_session_id:
            cmd += ["--resume", session.claude_session_id]
        return cmd

    def _parse_chunk(
        self, text: str, session: ChatSession,
    ) -> dict | None:
        """Parse a stream-json line from Claude."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {"type": "text", "content": text}
        if "session_id" in data and not session.claude_session_id:
            session.claude_session_id = data["session_id"]
        msg_type = data.get("type", "")
        if msg_type == "assistant":
            return self._extract_assistant(data)
        if msg_type == "result":
            content = data.get("result", "")
            return {"type": "result", "content": content}
        return None

    def _extract_assistant(self, data: dict) -> dict:
        """Extract text from assistant message."""
        content = data.get("message", {}).get("content", "")
        if isinstance(content, list):
            parts = [
                b.get("text", "")
                for b in content
                if b.get("type") == "text"
            ]
            return {"type": "text", "content": "".join(parts)}
        return {"type": "text", "content": str(content)}

    def _resolve_project(self, project_key: str) -> str:
        """Map project_key to validated working directory."""
        for cb in self.cfg.codebases:
            if cb.key == project_key:
                path = Path(cb.path).expanduser().resolve()
                return str(path)
        raise ValueError(
            f"Project '{project_key}' not found in codebases"
        )
