"""Scan local repos for unique GitHub org names."""

from __future__ import annotations

from pathlib import Path

from maggy.discovery import discover_repos, infer_github_org


def scan_orgs(home: Path | None = None) -> list[str]:
    """Return sorted unique GitHub org names from local repos."""
    repos = discover_repos(home)
    orgs: set[str] = set()
    for repo in repos:
        org = infer_github_org(Path(repo["path"]))
        if org:
            orgs.add(org)
    return sorted(orgs)


def effective_orgs(
    scanned: list[str],
    manual: list[str],
    excluded: list[str],
) -> list[str]:
    """Merge scanned + manual orgs, remove excluded."""
    combined = set(scanned) | set(manual)
    combined -= set(excluded)
    return sorted(combined)
