"""Tests for environment auto-discovery."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from maggy.discovery import (
    DiscoveryResult,
    _parse_org_from_url,
    discover_active_projects,
    discover_clis,
    discover_env_tokens,
    discover_repos,
    full_discovery,
)
from maggy.process.discovery import discover_local


class TestDiscoverLocal:
    def test_empty_project(self, tmp_path: Path):
        result = discover_local(tmp_path)
        assert result["ci"] == []
        assert result["quality"] == []
        assert result["review"] == []
        assert result["deps"] == []

    def test_detects_github_actions(self, tmp_path: Path):
        (tmp_path / ".github" / "workflows").mkdir(parents=True)
        result = discover_local(tmp_path)
        assert "github_actions" in result["ci"]

    def test_detects_jenkins(self, tmp_path: Path):
        (tmp_path / "Jenkinsfile").touch()
        result = discover_local(tmp_path)
        assert "jenkins" in result["ci"]

    def test_detects_circleci(self, tmp_path: Path):
        (tmp_path / ".circleci").mkdir()
        result = discover_local(tmp_path)
        assert "circleci" in result["ci"]

    def test_detects_gitlab_ci(self, tmp_path: Path):
        (tmp_path / ".gitlab-ci.yml").touch()
        result = discover_local(tmp_path)
        assert "gitlab_ci" in result["ci"]

    def test_detects_eslint(self, tmp_path: Path):
        (tmp_path / ".eslintrc.json").touch()
        result = discover_local(tmp_path)
        assert "eslint" in result["quality"]

    def test_detects_ruff_in_pyproject(self, tmp_path: Path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.ruff]\nline-length = 88\n")
        result = discover_local(tmp_path)
        assert "ruff" in result["quality"]

    def test_detects_pre_commit(self, tmp_path: Path):
        (tmp_path / ".pre-commit-config.yaml").touch()
        result = discover_local(tmp_path)
        assert "pre-commit" in result["quality"]

    def test_detects_codeowners(self, tmp_path: Path):
        (tmp_path / "CODEOWNERS").touch()
        result = discover_local(tmp_path)
        assert "codeowners" in result["review"]

    def test_detects_dependabot(self, tmp_path: Path):
        (tmp_path / ".github").mkdir(parents=True)
        (tmp_path / ".github" / "dependabot.yml").touch()
        result = discover_local(tmp_path)
        assert "dependabot" in result["deps"]

    def test_detects_renovate(self, tmp_path: Path):
        (tmp_path / "renovate.json").touch()
        result = discover_local(tmp_path)
        assert "renovate" in result["deps"]


# --- CLI Discovery ---


class TestDiscoverClis:
    def test_finds_installed(self):
        def _which(n):
            return f"/usr/bin/{n}" if n == "claude" else None

        with patch("shutil.which", side_effect=_which):
            result = discover_clis()
        assert result == {"claude": "/usr/bin/claude"}

    def test_finds_none(self):
        with patch("shutil.which", return_value=None):
            result = discover_clis()
        assert result == {}

    def test_finds_all(self):
        with patch("shutil.which", side_effect=lambda n: f"/usr/bin/{n}"):
            result = discover_clis()
        assert len(result) == 3
        assert "claude" in result


# --- Repo Discovery ---


class TestDiscoverRepos:
    def test_finds_git_repos(self, tmp_path: Path):
        docs = tmp_path / "Documents"
        docs.mkdir()
        repo = docs / "my-proj"
        repo.mkdir()
        (repo / ".git").mkdir()

        repos = discover_repos(home=tmp_path)
        assert len(repos) == 1
        assert repos[0]["key"] == "my-proj"

    def test_skips_hidden_dirs(self, tmp_path: Path):
        docs = tmp_path / "Documents"
        docs.mkdir()
        hidden = docs / ".secret"
        hidden.mkdir()
        (hidden / ".git").mkdir()

        repos = discover_repos(home=tmp_path)
        assert repos == []

    def test_depth_limited(self, tmp_path: Path):
        dev = tmp_path / "dev"
        deep = dev / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        (deep / ".git").mkdir()

        repos = discover_repos(home=tmp_path)
        assert repos == []

    def test_max_30_repos(self, tmp_path: Path):
        dev = tmp_path / "dev"
        dev.mkdir()
        for i in range(35):
            r = dev / f"repo-{i:02d}"
            r.mkdir()
            (r / ".git").mkdir()

        repos = discover_repos(home=tmp_path)
        assert len(repos) == 30

    def test_no_scan_dirs(self, tmp_path: Path):
        repos = discover_repos(home=tmp_path)
        assert repos == []


# --- Active Projects ---


class TestDiscoverActiveProjects:
    def test_parses_history(self, tmp_path: Path):
        lines = [
            json.dumps({"project": "/Users/me/proj-a"}),
            json.dumps({"project": "/Users/me/proj-a"}),
            json.dumps({"project": "/Users/me/proj-b"}),
        ]
        (tmp_path / "history.jsonl").write_text(
            "\n".join(lines) + "\n",
        )

        projects = discover_active_projects(tmp_path)
        assert projects[0] == "proj-a"
        assert "proj-b" in projects

    def test_no_history_file(self, tmp_path: Path):
        result = discover_active_projects(tmp_path)
        assert result == []

    def test_malformed_json(self, tmp_path: Path):
        content = "not-json\n{\"project\":\"/p\"}\n"
        (tmp_path / "history.jsonl").write_text(content)

        projects = discover_active_projects(tmp_path)
        assert projects == ["p"]


# --- Env Tokens ---


class TestDiscoverEnvTokens:
    def test_detects_tokens(self):
        env = {"GITHUB_TOKEN": "ghp_abc"}
        with patch.dict("os.environ", env, clear=True):
            result = discover_env_tokens()
        assert result["GITHUB_TOKEN"] is True
        assert result["ANTHROPIC_API_KEY"] is False

    def test_no_env_tokens(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch("maggy.discovery.discover_git_token", return_value=""):
                result = discover_env_tokens()
        assert result["GITHUB_TOKEN"] is False
        assert result["ANTHROPIC_API_KEY"] is False
        assert result["ASANA_API_KEY"] is False


# --- URL Parsing ---


class TestParseOrgFromUrl:
    def test_ssh_url(self):
        url = "git@github.com:acme/webapp.git"
        assert _parse_org_from_url(url) == "acme"

    def test_https_url(self):
        url = "https://github.com/acme/webapp.git"
        assert _parse_org_from_url(url) == "acme"

    def test_non_github(self):
        url = "https://gitlab.com/acme/webapp.git"
        assert _parse_org_from_url(url) == ""


# --- Full Discovery ---


class TestFullDiscovery:
    def test_returns_result(self, tmp_path: Path):
        with patch("shutil.which", return_value=None):
            result = full_discovery(home=tmp_path)
        assert isinstance(result, DiscoveryResult)
        assert result.timestamp != ""

    def test_populates_repos(self, tmp_path: Path):
        dev = tmp_path / "dev"
        dev.mkdir()
        repo = dev / "my-app"
        repo.mkdir()
        (repo / ".git").mkdir()

        with patch("shutil.which", return_value=None):
            result = full_discovery(home=tmp_path)
        assert len(result.repos) == 1
        assert result.repos[0]["key"] == "my-app"
