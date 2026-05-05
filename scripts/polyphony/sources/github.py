"""GitHub Issues work source (§2).

Polls GitHub Issues via `gh api` for tasks labeled agent-ready.
"""

from __future__ import annotations

import json
import subprocess

from ..models import Task


class GitHubSource:
    """GitHub Issues as task source."""

    def __init__(
        self,
        repo: str = "",
        label_filter: str = "agent-ready",
    ):
        self._repo = repo
        self._label = label_filter

    def poll(self) -> list[Task]:
        """Fetch open issues matching the label filter."""
        cmd = [
            "gh", "api",
            f"repos/{self._repo}/issues",
            "--jq", ".",
            "-q", f"label:{self._label}",
        ]
        result = _run_gh(cmd)
        if result.returncode != 0:
            return []
        try:
            issues = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return []
        return [self._issue_to_task(i) for i in issues]

    def _issue_to_task(self, issue: dict) -> Task:
        """Convert a GitHub issue dict to a Task."""
        return Task(
            title=issue.get("title", ""),
            source="github",
            source_ref=f"{self._repo}#{issue.get('number', '')}",
        )


def _run_gh(cmd: list[str]) -> subprocess.CompletedProcess:
    """Run a gh CLI command. Thin wrapper for mocking."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
