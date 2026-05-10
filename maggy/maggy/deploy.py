"""Deploy orchestrator — manages Vercel session containers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class DeploySession:
    """Represents a running deploy session."""

    session_id: str
    project: str
    branch: str
    status: str = "pending"  # pending | building | live | failed
    url: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


class DeployService:
    """Manages deploy sessions (stub for container orchestration)."""

    def __init__(self):
        self._sessions: dict[str, DeploySession] = {}

    def create_session(
        self, project: str, branch: str,
    ) -> DeploySession:
        """Create a new deploy session."""
        import uuid
        sid = str(uuid.uuid4())[:8]
        session = DeploySession(
            session_id=sid,
            project=project,
            branch=branch,
            status="building",
        )
        self._sessions[sid] = session
        logger.info("Deploy session %s created for %s:%s",
                     sid, project, branch)
        return session

    def get_session(self, sid: str) -> DeploySession | None:
        return self._sessions.get(sid)

    def list_sessions(self) -> list[DeploySession]:
        return list(self._sessions.values())

    def update_status(
        self, sid: str, status: str, url: str = "",
    ) -> DeploySession | None:
        """Update session status."""
        session = self._sessions.get(sid)
        if not session:
            return None
        session.status = status
        if url:
            session.url = url
        return session

    def teardown(self, sid: str) -> bool:
        """Remove a deploy session."""
        if sid in self._sessions:
            del self._sessions[sid]
            return True
        return False
