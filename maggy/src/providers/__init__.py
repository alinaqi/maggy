"""Issue tracker provider abstractions."""

from .asana import AsanaProvider
from .base import Comment, IssueTrackerProvider, Task
from .github_issues import GitHubIssuesProvider

__all__ = [
    "AsanaProvider",
    "Comment",
    "GitHubIssuesProvider",
    "IssueTrackerProvider",
    "Task",
]


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
