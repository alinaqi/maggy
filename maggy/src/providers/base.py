"""IssueTrackerProvider Protocol — all trackers (GitHub, Asana, Linear) implement this.

Services call provider.list_tasks() and work with Task/Comment dataclasses. They
don't care which tracker is underneath. Swap providers without touching services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Task:
    """Provider-agnostic task representation.

    Fields that don't apply to a given provider are left empty — never None for strings
    so downstream formatters don't need null checks.
    """
    id: str                        # Provider-native ID ("123" for GH, "1213..." for Asana)
    title: str
    description: str = ""          # Full body/notes
    status: str = ""               # "open", "closed", "in progress", etc.
    assignee: str = ""             # Display name
    author: str = ""               # Who created it
    url: str = ""                  # Permalink
    labels: list[str] = field(default_factory=list)
    board: str = ""                # Project/repo name
    created_at: str = ""           # ISO 8601
    updated_at: str = ""           # ISO 8601
    raw: dict = field(default_factory=dict)  # Original provider payload for escape hatches


@dataclass
class Comment:
    id: str
    author: str
    text: str
    created_at: str = ""


class IssueTrackerProvider(Protocol):
    """Common interface across GitHub Issues, Asana, Linear, etc."""

    async def list_tasks(self, board: str | None = None, state: str = "open", limit: int = 50) -> list[Task]:
        """List tasks. `board` filters to a specific project/repo if provider supports it."""
        ...

    async def get_task(self, task_id: str) -> Task | None:
        ...

    async def get_comments(self, task_id: str) -> list[Comment]:
        ...

    async def add_comment(self, task_id: str, text: str) -> Comment | None:
        ...

    async def update_status(self, task_id: str, status: str) -> bool:
        """Update status. For providers that use labels (GitHub), this maps intelligently."""
        ...

    async def list_followed(self, user_id: str | None = None, limit: int = 50) -> list[Task]:
        """Tasks the user is watching/following/assigned to — powers the 'Latest' tab."""
        ...

    async def search_tasks(self, query: str, limit: int = 20) -> list[Task]:
        ...

    def provider_name(self) -> str:
        """Return 'github' | 'asana' | 'linear' — for UI display."""
        ...
