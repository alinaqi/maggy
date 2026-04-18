"""Asana provider — compatibility shim for teams migrating from the zenloop prototype."""

from __future__ import annotations

import httpx

from .base import Comment, IssueTrackerProvider, Task

ASANA_BASE = "https://app.asana.com/api/1.0"


class AsanaProvider:
    """IssueTrackerProvider implementation for Asana.

    Simpler than the zenloop prototype — no USER_GIDS hardcoded. `list_followed`
    uses the authenticated user's GID via /users/me.
    """

    def __init__(self, workspace_id: str, boards: dict[str, str], token: str):
        self.workspace_id = workspace_id
        # boards: {"dev": "project_gid", "bugs": "other_gid"}
        self.boards = boards
        self.token = token
        self._my_gid: str = ""

    def provider_name(self) -> str:
        return "asana"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _to_task(self, t: dict) -> Task:
        assignee = (t.get("assignee") or {}).get("name", "")
        projects = t.get("projects") or []
        board = projects[0].get("name", "") if projects else ""
        return Task(
            id=t.get("gid", ""),
            title=t.get("name", ""),
            description=t.get("notes", "") or "",
            status="closed" if t.get("completed") else "open",
            assignee=assignee,
            url=t.get("permalink_url", ""),
            labels=[tag.get("name", "") for tag in (t.get("tags") or [])],
            board=board,
            created_at=t.get("created_at", ""),
            updated_at=t.get("modified_at", ""),
            raw=t,
        )

    async def _get_my_gid(self, client: httpx.AsyncClient) -> str:
        if self._my_gid:
            return self._my_gid
        resp = await client.get(f"{ASANA_BASE}/users/me", headers=self._headers())
        if resp.status_code == 200:
            self._my_gid = resp.json().get("data", {}).get("gid", "")
        return self._my_gid

    async def list_tasks(self, board: str | None = None, state: str = "open", limit: int = 50) -> list[Task]:
        if not self.boards:
            return []

        # Which boards to query
        board_gids: list[str]
        if board and board in self.boards:
            board_gids = [self.boards[board]]
        else:
            board_gids = list(self.boards.values())

        tasks: list[Task] = []
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            for gid in board_gids:
                # `completed_since=now` tells Asana to exclude tasks completed
                # before this instant (i.e. give us open + just-now-completed).
                # Don't send it at all when we WANT completed tasks — empty
                # string is rejected by Asana's validator.
                params = {
                    "opt_fields": "name,notes,completed,assignee.name,projects.name,modified_at,created_at,permalink_url,tags.name",
                    "limit": str(min(limit, 100)),
                }
                if state == "open":
                    params["completed_since"] = "now"
                resp = await client.get(f"{ASANA_BASE}/projects/{gid}/tasks", params=params)
                if resp.status_code != 200:
                    continue
                for t in resp.json().get("data", []):
                    # completed_since gives everything after a timestamp — we
                    # still need to filter to match the requested state.
                    if state == "open" and t.get("completed"):
                        continue
                    if state == "closed" and not t.get("completed"):
                        continue
                    tasks.append(self._to_task(t))

        tasks.sort(key=lambda t: t.updated_at, reverse=True)
        return tasks[:limit]

    async def get_task(self, task_id: str) -> Task | None:
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            resp = await client.get(
                f"{ASANA_BASE}/tasks/{task_id}",
                params={"opt_fields": "name,notes,completed,assignee.name,projects.name,modified_at,created_at,permalink_url,tags.name"},
            )
            if resp.status_code != 200:
                return None
            return self._to_task(resp.json().get("data", {}))

    async def get_comments(self, task_id: str) -> list[Comment]:
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            resp = await client.get(
                f"{ASANA_BASE}/tasks/{task_id}/stories",
                params={"opt_fields": "type,text,created_at,created_by.name,resource_subtype"},
            )
            if resp.status_code != 200:
                return []
            out: list[Comment] = []
            for s in resp.json().get("data", []):
                if s.get("resource_subtype") != "comment_added":
                    continue
                out.append(Comment(
                    id=s.get("gid", ""),
                    author=(s.get("created_by") or {}).get("name", ""),
                    text=s.get("text", ""),
                    created_at=s.get("created_at", ""),
                ))
            return out

    async def add_comment(self, task_id: str, text: str) -> Comment | None:
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            resp = await client.post(
                f"{ASANA_BASE}/tasks/{task_id}/stories",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"data": {"text": text}},
            )
            if resp.status_code not in (200, 201):
                return None
            d = resp.json().get("data", {})
            return Comment(
                id=d.get("gid", ""),
                author=(d.get("created_by") or {}).get("name", ""),
                text=d.get("text", text),
                created_at=d.get("created_at", ""),
            )

    async def update_status(self, task_id: str, status: str) -> bool:
        completed = status.lower().strip() in ("done", "closed", "complete", "completed", "resolved")
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            resp = await client.put(
                f"{ASANA_BASE}/tasks/{task_id}",
                headers={**self._headers(), "Content-Type": "application/json"},
                json={"data": {"completed": completed}},
            )
            return resp.status_code == 200

    async def list_followed(self, user_id: str | None = None, limit: int = 50) -> list[Task]:
        if not self.workspace_id:
            return []
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            gid = user_id or await self._get_my_gid(client)
            if not gid:
                return []
            resp = await client.get(
                f"{ASANA_BASE}/workspaces/{self.workspace_id}/tasks/search",
                params={
                    "followers.any": gid,
                    "completed": "false",
                    "sort_by": "modified_at",
                    "opt_fields": "name,notes,assignee.name,projects.name,modified_at,permalink_url",
                    "limit": str(min(limit, 100)),
                },
            )
            if resp.status_code != 200:
                return []
            return [self._to_task(t) for t in resp.json().get("data", [])]

    async def search_tasks(self, query: str, limit: int = 20) -> list[Task]:
        if not self.workspace_id:
            return []
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            resp = await client.get(
                f"{ASANA_BASE}/workspaces/{self.workspace_id}/tasks/search",
                params={
                    "text": query,
                    "opt_fields": "name,notes,completed,assignee.name,projects.name,modified_at,permalink_url",
                    "limit": str(min(limit, 100)),
                },
            )
            if resp.status_code != 200:
                return []
            return [self._to_task(t) for t in resp.json().get("data", [])]
