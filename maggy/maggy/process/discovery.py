"""Environment auto-discovery — detects CI/CD, review tools, etc."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def discover_local(project_path: Path) -> dict:
    """Discover tools from local filesystem markers."""
    result: dict[str, list[str]] = {
        "ci": [], "quality": [], "review": [], "deps": [],
    }

    # CI/CD
    gh_workflows = project_path / ".github" / "workflows"
    if gh_workflows.exists():
        result["ci"].append("github_actions")

    if (project_path / "Jenkinsfile").exists():
        result["ci"].append("jenkins")

    if (project_path / ".circleci").exists():
        result["ci"].append("circleci")

    if (project_path / ".gitlab-ci.yml").exists():
        result["ci"].append("gitlab_ci")

    # Code quality
    if (project_path / ".eslintrc.json").exists() or \
       (project_path / ".eslintrc.js").exists():
        result["quality"].append("eslint")

    if (project_path / "pyproject.toml").exists():
        content = (project_path / "pyproject.toml").read_text()
        if "ruff" in content:
            result["quality"].append("ruff")
        if "mypy" in content:
            result["quality"].append("mypy")

    if (project_path / ".pre-commit-config.yaml").exists():
        result["quality"].append("pre-commit")

    # Review tools
    if (project_path / "CODEOWNERS").exists() or \
       (project_path / ".github" / "CODEOWNERS").exists():
        result["review"].append("codeowners")

    # Dependency management
    dependabot = project_path / ".github" / "dependabot.yml"
    if dependabot.exists():
        result["deps"].append("dependabot")

    renovate = project_path / "renovate.json"
    if renovate.exists():
        result["deps"].append("renovate")

    return result


async def discover_github(
    repo: str, token: str,
) -> dict:
    """Discover integrations via GitHub API."""
    result: dict[str, list[str]] = {
        "bots": [], "protection": [],
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(
        timeout=10.0, headers=headers,
    ) as client:
        # Check branch protection
        try:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo}/branches/main"
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("protected"):
                    result["protection"].append(
                        "branch_protection"
                    )
        except httpx.HTTPError:
            pass

        # Check recent PR comments for bots
        try:
            resp = await client.get(
                f"{GITHUB_API}/repos/{repo}/pulls",
                params={"state": "all", "per_page": "5"},
            )
            if resp.status_code == 200:
                for pr in resp.json()[:3]:
                    cr = await client.get(
                        f"{GITHUB_API}/repos/{repo}"
                        f"/pulls/{pr['number']}/comments",
                        params={"per_page": "10"},
                    )
                    if cr.status_code == 200:
                        for c in cr.json():
                            user = (c.get("user") or {}).get(
                                "login", ""
                            ).lower()
                            if "coderabbit" in user:
                                result["bots"].append(
                                    "coderabbit"
                                )
                            if "dependabot" in user:
                                result["bots"].append(
                                    "dependabot"
                                )
                # Deduplicate
                result["bots"] = list(set(result["bots"]))
        except httpx.HTTPError:
            pass

    return result
