"""Issue tracker provider abstractions."""

from .base import IssueTrackerProvider, Task, Comment
from .github_issues import GitHubIssuesProvider
from .asana import AsanaProvider

__all__ = ["IssueTrackerProvider", "Task", "Comment", "GitHubIssuesProvider", "AsanaProvider"]


def build(cfg) -> IssueTrackerProvider:
    """Factory: build the right provider from MaggyConfig."""
    from src.config import MaggyConfig

    if cfg.issue_tracker.provider == "github":
        gh = cfg.issue_tracker.github
        return GitHubIssuesProvider(org=gh.org, repos=gh.repos, token=gh.token, labels=gh.labels)
    if cfg.issue_tracker.provider == "asana":
        az = cfg.issue_tracker.asana
        return AsanaProvider(workspace_id=az.workspace_id, boards=az.boards, token=az.token)
    raise ValueError(f"Unknown issue tracker provider: {cfg.issue_tracker.provider}")
