"""Project bootstrap — detect CLIs, dev tools, git, cortex, project stack."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_GIT_TIMEOUT = 5


@dataclass
class CliStatus:
    name: str
    installed: bool
    version: str = ""
    path: str = ""
    category: str = ""


@dataclass
class GitState:
    is_repo: bool = False
    branch: str = ""
    has_uncommitted: bool = False
    recent_branches: list[str] = field(default_factory=list)


@dataclass
class ProjectStatus:
    clis: list[CliStatus] = field(default_factory=list)
    tools: list[CliStatus] = field(default_factory=list)
    git: GitState = field(default_factory=GitState)
    cortex: dict = field(default_factory=dict)
    stack: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "clis": [_cli_dict(c) for c in self.clis],
            "tools": [_cli_dict(c) for c in self.tools],
            "git": _git_dict(self.git),
            "cortex": self.cortex,
            "stack": self.stack,
        }


def _cli_dict(c: CliStatus) -> dict:
    return {"name": c.name, "installed": c.installed,
            "version": c.version, "path": c.path,
            "category": c.category}


def _git_dict(g: GitState) -> dict:
    return {"is_repo": g.is_repo, "branch": g.branch,
            "has_uncommitted": g.has_uncommitted,
            "recent_branches": g.recent_branches}


_AI_CLIS = [
    "claude", "codex", "kimi", "deepseek", "ollama",
    "gemini", "grok", "agy",
]

_DEV_TOOLS = [
    ("git", "vcs"), ("gh", "vcs"), ("npm", "pkg"), ("pip", "pkg"),
    ("uv", "pkg"), ("pnpm", "pkg"), ("yarn", "pkg"),
    ("ruff", "lint"), ("eslint", "lint"), ("mypy", "type"),
    ("pytest", "test"), ("vitest", "test"), ("jest", "test"),
    ("docker", "infra"), ("supabase", "infra"), ("vercel", "deploy"),
    ("railway", "deploy"), ("fly", "deploy"),
]

_BIN_DIR = os.path.expanduser("~/bin")


def _find_binary(name: str) -> str | None:
    """Find binary in PATH or ~/bin. Returns path or None."""
    binary = shutil.which(name)
    if binary:
        return binary
    bin_path = os.path.join(_BIN_DIR, name)
    if os.path.isfile(bin_path) and os.access(bin_path, os.X_OK):
        return bin_path
    return None


def detect_cli_inventory() -> list[CliStatus]:
    """Detect which AI CLIs are installed. Never raises."""
    results: list[CliStatus] = []
    for name in _AI_CLIS:
        binary = _find_binary(name)
        results.append(CliStatus(
            name=name, installed=binary is not None,
            path=binary or "", category="ai",
        ))
    return results


def detect_dev_tools() -> list[CliStatus]:
    """Detect development tools (git, gh, npm, etc). Never raises."""
    results: list[CliStatus] = []
    for name, category in _DEV_TOOLS:
        binary = _find_binary(name)
        results.append(CliStatus(
            name=name, installed=binary is not None,
            path=binary or "", category=category,
        ))
    return results


_STACK_MARKERS = {
    "python": ["pyproject.toml", "setup.py", "requirements.txt"],
    "node": ["package.json"],
    "rust": ["Cargo.toml"],
    "go": ["go.mod"],
    "ruby": ["Gemfile"],
    "elixir": ["mix.exs"],
}


def detect_project_stack(project_path: str) -> dict:
    """Detect project type and tooling from root files. Never raises."""
    if not os.path.isdir(project_path):
        return {"type": "unknown", "markers": []}
    root = Path(project_path)
    found_markers: list[str] = []
    stack_type = "unknown"
    for stype, markers in _STACK_MARKERS.items():
        for m in markers:
            if (root / m).exists():
                found_markers.append(m)
                stack_type = stype
    result: dict = {"type": stack_type, "markers": found_markers}
    result["test_runner"] = _detect_test_runner(root, stack_type)
    result["linter"] = _detect_linter(root, stack_type)
    return result


def _detect_test_runner(root: Path, stack: str) -> str:
    """Detect test runner from config files."""
    if stack == "python":
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            text = pyproject.read_text(errors="replace")
            if "pytest" in text:
                return "pytest"
        if (root / "pytest.ini").exists():
            return "pytest"
    if stack == "node":
        pkg = root / "package.json"
        if pkg.exists():
            text = pkg.read_text(errors="replace")
            if "vitest" in text:
                return "vitest"
            if "jest" in text:
                return "jest"
    return ""


def _detect_linter(root: Path, stack: str) -> str:
    """Detect linter from config files."""
    if stack == "python":
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            text = pyproject.read_text(errors="replace")
            if "ruff" in text:
                return "ruff"
    if stack == "node":
        if (root / ".eslintrc.json").exists():
            return "eslint"
        if (root / "eslint.config.js").exists():
            return "eslint"
    return ""


def detect_git_state(project_path: str) -> GitState:
    """Detect git repo state. Never raises."""
    state = GitState()
    if not os.path.isdir(project_path):
        return state
    git_dir = os.path.join(project_path, ".git")
    if not os.path.exists(git_dir):
        return state
    state.is_repo = True
    state.branch = _git_cmd(project_path, "branch", "--show-current")
    status = _git_cmd(project_path, "status", "--porcelain")
    state.has_uncommitted = bool(status.strip())
    state.recent_branches = _recent_branches(project_path)
    return state


def _git_cmd(cwd: str, *args: str) -> str:
    """Run a git command, return stdout. Never raises."""
    try:
        r = subprocess.run(
            ["git", *args], cwd=cwd,
            capture_output=True, text=True,
            timeout=_GIT_TIMEOUT,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _recent_branches(project_path: str) -> list[str]:
    """Get recently updated branches (max 5)."""
    raw = _git_cmd(
        project_path, "branch", "--sort=-committerdate",
        "--format=%(refname:short)",
    )
    if not raw:
        return []
    return [b.strip() for b in raw.splitlines()[:5] if b.strip()]


def detect_cortex_state(project_path: str) -> dict:
    """Check if cortex/iCPG data exists. Never raises."""
    if not os.path.isdir(project_path):
        return {"exists": False, "has_graph": False}
    cortex = Path(project_path) / ".cortex"
    if not cortex.is_dir():
        return {"exists": False, "has_graph": False}
    graph = cortex / "graph.db"
    return {
        "exists": True,
        "has_graph": graph.exists(),
        "files": len(list(cortex.iterdir())),
    }


def run_bootstrap(project_path: str) -> ProjectStatus:
    """Run full bootstrap detection. Never raises."""
    status = ProjectStatus()
    try:
        status.clis = detect_cli_inventory()
    except Exception as e:
        logger.debug("CLI detection failed: %s", e)
    try:
        status.tools = detect_dev_tools()
    except Exception as e:
        logger.debug("Dev tools detection failed: %s", e)
    try:
        status.git = detect_git_state(project_path)
    except Exception as e:
        logger.debug("Git detection failed: %s", e)
    try:
        status.cortex = detect_cortex_state(project_path)
    except Exception as e:
        logger.debug("Cortex detection failed: %s", e)
        status.cortex = {"exists": False}
    try:
        status.stack = detect_project_stack(project_path)
    except Exception as e:
        logger.debug("Stack detection failed: %s", e)
        status.stack = {"type": "unknown"}
    return status
