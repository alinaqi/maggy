"""GitHub Issues provider — talks to GitHub REST API across multiple repos."""

from __future__ import annotations

import httpx

from .base import Comment, IssueTrackerProvider, Task

GITHUB_API = "https://api.github.com"


class GitHubIssuesProvider:
    """IssueTrackerProvider implementation for GitHub Issues.

    Handles multiple repos transparently — list_tasks() aggregates across all
    configured repos. Task IDs are encoded as "repo/number" (e.g. "api/123") so
    we can round-trip back to the right repo.
    """

    def __init__(self, org: str, repos: list[str], token: str, labels: list[str] | None = None):
        self.org = org
        self.repos = repos  # Full names: ["org/api", "org/web"]
        self.token = token
        self.label_filter = labels or []

    def provider_name(self) -> str:
        return "github"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _encode_id(self, repo: str, number: int) -> str:
        # Store repo slug (without org prefix for compactness) + issue number
        slug = repo.split("/")[-1]
        return f"{slug}/{number}"

    def _decode_id(self, task_id: str) -> tuple[str, int] | None:
        """Parse 'slug/number' IDs. Returns None for malformed input.

        Returning None (instead of raising) lets the caller translate to a
        404/None response instead of a 500 to the client.
        """
        if not task_id or "/" not in task_id:
            return None
        slug, _, num_str = task_id.partition("/")
        if not num_str.isdigit():
            return None
        number = int(num_str)
        for repo in self.repos:
            if repo.endswith("/" + slug):
                return repo, number
        # Fallback: assume org prefix (for repos not in the configured list)
        if self.org:
            return f"{self.org}/{slug}", number
        return None

    def _to_task(self, repo: str, issue: dict) -> Task:
        return Task(
            id=self._encode_id(repo, issue["number"]),
            title=issue.get("title", ""),
            description=issue.get("body") or "",
            status=issue.get("state", "open"),
            assignee=((issue.get("assignee") or {}) or {}).get("login", ""),
            author=((issue.get("user") or {}) or {}).get("login", ""),
            url=issue.get("html_url", ""),
            labels=[lbl["name"] for lbl in issue.get("labels", []) if isinstance(lbl, dict)],
            board=repo.split("/")[-1],
            created_at=issue.get("created_at", ""),
            updated_at=issue.get("updated_at", ""),
            raw=issue,
        )

    async def list_tasks(self, board: str | None = None, state: str = "open", limit: int = 50) -> list[Task]:
        """List issues across repos (or one repo if `board` given). Excludes PRs."""
        repos = [r for r in self.repos if not board or r.endswith("/" + board)]
        if not repos:
            return []

        per_repo = max(1, limit // max(len(repos), 1))
        tasks: list[Task] = []

        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            for repo in repos:
                params: dict[str, str] = {"state": state, "per_page": str(per_repo), "sort": "updated"}
                if self.label_filter:
                    params["labels"] = ",".join(self.label_filter)
                resp = await client.get(f"{GITHUB_API}/repos/{repo}/issues", params=params)
                if resp.status_code != 200:
                    continue
                for issue in resp.json():
                    # GitHub returns PRs in /issues — filter them out
                    if "pull_request" in issue:
                        continue
                    tasks.append(self._to_task(repo, issue))

        tasks.sort(key=lambda t: t.updated_at, reverse=True)
        return tasks[:limit]

    async def get_task(self, task_id: str) -> Task | None:
        decoded = self._decode_id(task_id)
        if decoded is None:
            return None
        repo, number = decoded
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            resp = await client.get(f"{GITHUB_API}/repos/{repo}/issues/{number}")
            if resp.status_code != 200:
                return None
            return self._to_task(repo, resp.json())

    async def get_comments(self, task_id: str) -> list[Comment]:
        decoded = self._decode_id(task_id)
        if decoded is None:
            return []
        repo, number = decoded
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            resp = await client.get(f"{GITHUB_API}/repos/{repo}/issues/{number}/comments")
            if resp.status_code != 200:
                return []
            return [
                Comment(
                    id=str(c["id"]),
                    author=((c.get("user") or {}) or {}).get("login", ""),
                    text=c.get("body", ""),
                    created_at=c.get("created_at", ""),
                )
                for c in resp.json()
            ]

    async def add_comment(self, task_id: str, text: str) -> Comment | None:
        decoded = self._decode_id(task_id)
        if decoded is None:
            return None
        repo, number = decoded
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{repo}/issues/{number}/comments",
                json={"body": text},
            )
            if resp.status_code not in (200, 201):
                return None
            c = resp.json()
            return Comment(
                id=str(c["id"]),
                author=((c.get("user") or {}) or {}).get("login", ""),
                text=c.get("body", ""),
                created_at=c.get("created_at", ""),
            )

    async def update_status(self, task_id: str, status: str) -> bool:
        """GitHub issues only have open/closed — map any "done-like" status to closed."""
        decoded = self._decode_id(task_id)
        if decoded is None:
            return False
        repo, number = decoded
        normalized = status.lower().strip()
        new_state = "closed" if normalized in ("done", "closed", "complete", "completed", "resolved") else "open"
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            resp = await client.patch(
                f"{GITHUB_API}/repos/{repo}/issues/{number}",
                json={"state": new_state},
            )
            return resp.status_code == 200

    async def list_followed(self, user_id: str | None = None, limit: int = 50) -> list[Task]:
        """Issues assigned to or mentioning the authenticated user across configured repos."""
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            # Figure out the user if not provided
            if not user_id:
                me = await client.get(f"{GITHUB_API}/user")
                if me.status_code == 200:
                    user_id = me.json().get("login", "")
                else:
                    return []

            # Use search API: is:open + assignee/mentions + repo filter
            repo_qual = " ".join(f"repo:{r}" for r in self.repos)
            query = f"is:issue is:open ({repo_qual}) (assignee:{user_id} OR mentions:{user_id})"
            resp = await client.get(
                f"{GITHUB_API}/search/issues",
                params={"q": query, "sort": "updated", "per_page": str(limit)},
            )
            if resp.status_code != 200:
                return []

            tasks: list[Task] = []
            for issue in resp.json().get("items", []):
                if "pull_request" in issue:
                    continue
                # Derive repo from URL
                repo_url = issue.get("repository_url", "")
                repo = "/".join(repo_url.rstrip("/").split("/")[-2:])
                tasks.append(self._to_task(repo, issue))
            return tasks

    async def search_tasks(self, query: str, limit: int = 20) -> list[Task]:
        async with httpx.AsyncClient(timeout=15, headers=self._headers()) as client:
            repo_qual = " ".join(f"repo:{r}" for r in self.repos)
            q = f"is:issue {query} {repo_qual}"
            resp = await client.get(
                f"{GITHUB_API}/search/issues",
                params={"q": q, "per_page": str(limit)},
            )
            if resp.status_code != 200:
                return []
            tasks: list[Task] = []
            for issue in resp.json().get("items", []):
                if "pull_request" in issue:
                    continue
                repo_url = issue.get("repository_url", "")
                repo = "/".join(repo_url.rstrip("/").split("/")[-2:])
                tasks.append(self._to_task(repo, issue))
            return tasks
