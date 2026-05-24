"""PR comment learner — extract feedback from GitHub PR reviews."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil

logger = logging.getLogger(__name__)

_GH_BIN = shutil.which("gh") or "gh"


def _parse_github_remote(remote_url: str) -> tuple[str, str] | None:
    m = re.match(r"git@github\.com:([^/]+)/([^/.]+?)(?:\.git)?$", remote_url)
    if m:
        return m.group(1), m.group(2)
    m = re.match(r"https://github\.com/([^/]+)/([^/.]+?)(?:\.git)?$", remote_url)
    if m:
        return m.group(1), m.group(2)
    return None


async def _check_gh_auth() -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            _GH_BIN, "auth", "status",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()
        return proc.returncode == 0
    except FileNotFoundError:
        return False


async def _get_remote_url(repo_path: str) -> str | None:
    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "remote", "get-url", "origin",
            cwd=repo_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        return stdout.decode().strip()
    except Exception:
        return None


async def fetch_pr_comments(
    repo_path: str, limit: int = 5,
) -> list[dict]:
    remote = await _get_remote_url(repo_path)
    if not remote:
        return []
    parsed = _parse_github_remote(remote)
    if not parsed:
        logger.debug("Not a GitHub remote: %s", remote)
        return []
    owner, repo = parsed
    if not await _check_gh_auth():
        logger.debug("gh CLI not authenticated")
        return []

    try:
        proc = await asyncio.create_subprocess_exec(
            _GH_BIN, "api", f"repos/{owner}/{repo}/pulls",
            "-q", f".[:{limit}].number",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.debug("gh api failed: %s", stderr.decode()[:100])
            return []
        nums = [
            int(n) for n in stdout.decode().strip().split("\n")
            if n.strip().isdigit()
        ]
    except Exception as exc:
        logger.debug("PR fetch error: %s", exc)
        return []

    all_comments: list[dict] = []
    for pr_num in nums[:limit]:
        try:
            proc = await asyncio.create_subprocess_exec(
                _GH_BIN, "api",
                f"repos/{owner}/{repo}/pulls/{pr_num}/comments",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            if proc.returncode == 0 and stdout.strip():
                comments = json.loads(stdout.decode())
                if isinstance(comments, list):
                    for c in comments:
                        c["pr_number"] = pr_num
                    all_comments.extend(comments)
        except Exception:
            continue
    return all_comments


def extract_pr_signals(comments: list[dict]) -> list[dict]:
    signals: list[dict] = []
    for comment in comments:
        body = comment.get("body", "")
        path = comment.get("path", "")
        if not body or len(body) < 20:
            continue
        signals.append({
            "memory_type": "feedback",
            "content": f"PR#{comment.get('pr_number', '?')} on {path}: {body[:200]}",
            "tags": ["pr-review", f"file:{path}"],
            "confidence": 0.85,
        })
    return signals[:10]
