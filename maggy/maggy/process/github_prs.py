"""GitHub PR fetcher — reads PRs, reviews, and CI checks.

Reuses patterns from providers/github_issues.py (httpx async,
headers, error handling). Fetches up to 200 PRs per repo.
"""

from __future__ import annotations

import logging

import httpx

from .models import CheckRecord, PRRecord, ReviewRecord

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
DEFAULT_TIMEOUT = 15


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def fetch_prs(
    repo: str,
    token: str,
    limit: int = 200,
) -> list[PRRecord]:
    """Fetch merged PRs with reviews and checks."""
    raw_prs = await _fetch_pr_list(repo, token, limit)
    records: list[PRRecord] = []

    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT, headers=_headers(token)
    ) as client:
        for pr_data in raw_prs:
            detail = await _fetch_pr_detail(
                client, repo, pr_data["number"]
            )
            pr = _parse_pr(detail or pr_data)
            pr.reviews = await _fetch_reviews(
                client, repo, pr.number
            )
            if pr.head_sha:
                pr.checks = await _fetch_checks(
                    client, repo, pr.head_sha
                )
            pr.files = await _fetch_files(
                client, repo, pr.number
            )
            records.append(pr)

    return records


async def _fetch_pr_list(
    repo: str,
    token: str,
    limit: int,
) -> list[dict]:
    """Paginate through /pulls endpoint."""
    results: list[dict] = []
    page = 1
    per_page = min(limit, 100)

    async with httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT, headers=_headers(token)
    ) as client:
        while len(results) < limit:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo}/pulls",
                params={
                    "state": "all",
                    "sort": "updated",
                    "direction": "desc",
                    "per_page": str(per_page),
                    "page": str(page),
                },
            )
            if resp.status_code != 200:
                _log_error(repo, "pulls", resp)
                break
            batch = resp.json()
            if not batch:
                break
            results.extend(batch)
            page += 1

    return results[:limit]


async def _fetch_pr_detail(
    client: httpx.AsyncClient,
    repo: str,
    pr_number: int,
) -> dict | None:
    """Fetch single PR detail (has additions/deletions)."""
    resp = await client.get(
        f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"
    )
    if resp.status_code != 200:
        return None
    return resp.json()


def _parse_pr(data: dict) -> PRRecord:
    """Convert raw GitHub PR JSON to PRRecord."""
    return PRRecord(
        number=data.get("number", 0),
        title=data.get("title", ""),
        author=(data.get("user") or {}).get("login", ""),
        state=_pr_state(data),
        created_at=data.get("created_at", ""),
        merged_at=data.get("merged_at"),
        additions=data.get("additions", 0),
        deletions=data.get("deletions", 0),
        changed_files=data.get("changed_files", 0),
        head_sha=(data.get("head") or {}).get("sha", ""),
        base_branch=(data.get("base") or {}).get("ref", ""),
    )


def _pr_state(data: dict) -> str:
    if data.get("merged_at"):
        return "merged"
    return data.get("state", "open")


async def _fetch_reviews(
    client: httpx.AsyncClient,
    repo: str,
    pr_number: int,
) -> list[ReviewRecord]:
    """Fetch all reviews for a PR."""
    resp = await client.get(
        f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/reviews"
    )
    if resp.status_code != 200:
        return []
    return [
        ReviewRecord(
            reviewer=(r.get("user") or {}).get("login", ""),
            state=r.get("state", ""),
            body=r.get("body") or "",
            submitted_at=r.get("submitted_at", ""),
        )
        for r in resp.json()
    ]


async def _fetch_checks(
    client: httpx.AsyncClient,
    repo: str,
    sha: str,
) -> list[CheckRecord]:
    """Fetch CI check runs for a commit."""
    resp = await client.get(
        f"{GITHUB_API}/repos/{repo}/commits/{sha}/check-runs"
    )
    if resp.status_code != 200:
        return []
    return [
        CheckRecord(
            name=c.get("name", ""),
            conclusion=c.get("conclusion") or "pending",
            started_at=c.get("started_at", ""),
            completed_at=c.get("completed_at") or "",
        )
        for c in resp.json().get("check_runs", [])
    ]


async def _fetch_files(
    client: httpx.AsyncClient,
    repo: str,
    pr_number: int,
) -> list[str]:
    """Fetch file paths changed in a PR."""
    resp = await client.get(
        f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files",
        params={"per_page": "100"},
    )
    if resp.status_code != 200:
        return []
    return [
        f.get("filename", "")
        for f in resp.json()
        if f.get("filename")
    ]


def _log_error(
    repo: str, endpoint: str, resp: httpx.Response
) -> None:
    body = (resp.text or "")[:200].replace("\n", " ")
    logger.warning(
        "GitHub /repos/%s/%s returned %s: %s",
        repo, endpoint, resp.status_code, body,
    )
