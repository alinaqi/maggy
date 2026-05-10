"""Auto-discovery — detects local CLIs, repos, and dev environment."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCAN_DIRS = [
    "Documents", "dev", "projects", "code", "src",
    "workspace", "repos", "work",
]

CLI_NAMES = ["claude", "codex", "kimi"]


@dataclass
class DiscoveryResult:
    """Everything auto-discovered about the local env."""

    clis: dict[str, str] = field(default_factory=dict)
    cli_auth: dict[str, bool] = field(
        default_factory=dict,
    )
    repos: list[dict] = field(default_factory=list)
    active_projects: list[str] = field(
        default_factory=list,
    )
    tokens: dict[str, bool] = field(
        default_factory=dict,
    )
    github_org: str = ""
    github_orgs: list[str] = field(
        default_factory=list,
    )
    timestamp: str = ""


def discover_clis() -> dict[str, str]:
    """Find installed CLI tools on PATH."""
    result: dict[str, str] = {}
    for name in CLI_NAMES:
        path = shutil.which(name)
        if path:
            result[name] = path
    return result


def discover_cli_auth() -> dict[str, bool]:
    """Check which CLIs have stored auth."""
    home = Path.home()
    auth: dict[str, bool] = {}
    # Claude Code: has projects dir = subscription active
    claude_dir = home / ".claude"
    auth["claude"] = (claude_dir / "projects").is_dir()
    # Codex: auth.json with tokens
    codex_auth = home / ".codex" / "auth.json"
    auth["codex"] = _has_json_key(codex_auth, "tokens")
    # Kimi: credentials directory with token files
    kimi_creds = home / ".kimi" / "credentials"
    auth["kimi"] = kimi_creds.is_dir() and any(
        kimi_creds.iterdir()
    )
    return auth


def _has_json_key(path: Path, key: str) -> bool:
    """Check if JSON file exists and has a key."""
    if not path.exists():
        return False
    try:
        with open(path) as f:
            return bool(json.load(f).get(key))
    except (json.JSONDecodeError, OSError):
        return False


def discover_git_token() -> str:
    """Read GitHub token from git credential helper."""
    try:
        result = subprocess.run(
            ["git", "credential", "fill"],
            input="protocol=https\nhost=github.com\n\n",
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.splitlines():
            if line.startswith("password="):
                return line.split("=", 1)[1]
    except (subprocess.SubprocessError, OSError):
        pass
    return ""


def discover_repos(
    home: Path | None = None,
) -> list[dict]:
    """Scan common directories for git repos."""
    root = home or Path.home()
    repos: list[dict] = []
    for dirname in SCAN_DIRS:
        parent = root / dirname
        if not parent.exists():
            continue
        _scan_dir(parent, repos, depth=0)
        if len(repos) >= 30:
            break
    return repos[:30]


def _scan_dir(
    parent: Path, repos: list[dict], depth: int,
) -> None:
    """Recursively scan for .git dirs up to depth 3."""
    if depth > 3 or len(repos) >= 30:
        return
    try:
        for child in sorted(parent.iterdir()):
            if not child.is_dir():
                continue
            if child.name.startswith("."):
                continue
            git_dir = child / ".git"
            if git_dir.is_dir():
                repos.append({
                    "path": str(child),
                    "key": child.name,
                })
            else:
                _scan_dir(child, repos, depth + 1)
    except PermissionError:
        pass


def discover_active_projects(
    claude_dir: Path | None = None,
) -> list[str]:
    """Rank projects by prompt count from Claude history."""
    cdir = claude_dir or (Path.home() / ".claude")
    history = cdir / "history.jsonl"
    if not history.exists():
        return []

    from collections import Counter
    counts: Counter[str] = Counter()
    try:
        for line in history.read_text().splitlines():
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                project = entry.get("project", "")
                if project:
                    name = Path(project).name
                    if name:
                        counts[name] += 1
            except json.JSONDecodeError:
                continue
    except OSError:
        return []

    return [p for p, _ in counts.most_common(15)]


def discover_env_tokens() -> dict[str, bool]:
    """Check env vars and git credential helper."""
    tokens = {
        "GITHUB_TOKEN": bool(
            os.environ.get("GITHUB_TOKEN"),
        ),
        "ANTHROPIC_API_KEY": bool(
            os.environ.get("ANTHROPIC_API_KEY"),
        ),
        "ASANA_API_KEY": bool(
            os.environ.get("ASANA_API_KEY"),
        ),
    }
    # Fall back to git credential helper for GitHub
    if not tokens["GITHUB_TOKEN"]:
        tokens["GIT_CREDENTIAL"] = bool(
            discover_git_token(),
        )
    return tokens


def infer_github_org(repo_path: Path) -> str:
    """Infer GitHub org from git remote URL."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True,
            cwd=str(repo_path), timeout=5,
        )
        url = result.stdout.strip()
        return _parse_org_from_url(url)
    except (subprocess.SubprocessError, OSError):
        return ""


def _parse_org_from_url(url: str) -> str:
    """Extract org from GitHub URL."""
    if "github.com:" in url:
        parts = url.split("github.com:")[-1]
        return parts.split("/")[0]
    if "github.com/" in url:
        parts = url.split("github.com/")[-1]
        return parts.split("/")[0]
    return ""


def discover_all_orgs(repos: list[dict]) -> list[str]:
    """Extract unique GitHub orgs from all repos."""
    orgs: set[str] = set()
    for repo in repos:
        org = infer_github_org(Path(repo["path"]))
        if org:
            orgs.add(org)
    return sorted(orgs)


def full_discovery(
    home: Path | None = None,
) -> DiscoveryResult:
    """Run all discovery checks."""
    clis = discover_clis()
    cli_auth = discover_cli_auth()
    repos = discover_repos(home)
    projects = discover_active_projects()
    tokens = discover_env_tokens()
    all_orgs = discover_all_orgs(repos)
    org = all_orgs[0] if all_orgs else ""

    return DiscoveryResult(
        clis=clis,
        cli_auth=cli_auth,
        repos=repos,
        active_projects=projects,
        tokens=tokens,
        github_org=org,
        github_orgs=all_orgs,
        timestamp=datetime.now(
            timezone.utc
        ).isoformat(),
    )
