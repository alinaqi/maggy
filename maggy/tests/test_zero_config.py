"""Tests for zero-config auto-configuration."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from maggy.config import MaggyConfig


# --- Provider Credentials ---


class TestHasProviderCredentials:
    def test_github_with_creds(self):
        from maggy.config import _has_provider_credentials
        cfg = MaggyConfig()
        cfg.issue_tracker.provider = "github"
        cfg.issue_tracker.github.org = "acme"
        cfg.issue_tracker.github.repos = ["api"]
        cfg.issue_tracker.github.token = "ghp_abc"
        assert _has_provider_credentials(cfg) is True

    def test_github_no_token(self):
        from maggy.config import _has_provider_credentials
        cfg = MaggyConfig()
        cfg.issue_tracker.provider = "github"
        cfg.issue_tracker.github.org = "acme"
        cfg.issue_tracker.github.repos = ["api"]
        assert _has_provider_credentials(cfg) is False

    def test_asana_with_creds(self):
        from maggy.config import _has_provider_credentials
        cfg = MaggyConfig()
        cfg.issue_tracker.provider = "asana"
        cfg.issue_tracker.asana.workspace_id = "w1"
        cfg.issue_tracker.asana.token = "tok"
        assert _has_provider_credentials(cfg) is True

    def test_linear_stub(self):
        from maggy.config import _has_provider_credentials
        cfg = MaggyConfig()
        cfg.issue_tracker.provider = "linear"
        assert _has_provider_credentials(cfg) is False


# --- CLI History Detection ---


class TestHasCliHistory:
    def test_claude_dir_exists(self, tmp_path: Path):
        from maggy.config import _has_cli_history
        (tmp_path / ".claude").mkdir()
        assert _has_cli_history(tmp_path) is True

    def test_no_dirs(self, tmp_path: Path):
        from maggy.config import _has_cli_history
        assert _has_cli_history(tmp_path) is False

    def test_codex_dir_exists(self, tmp_path: Path):
        from maggy.config import _has_cli_history
        (tmp_path / ".codex").mkdir()
        assert _has_cli_history(tmp_path) is True


# --- Auto Configure ---


class TestAutoConfigure:
    def test_builds_config(self, tmp_path: Path):
        from maggy.config import auto_configure
        with patch("shutil.which", return_value=None):
            cfg = auto_configure(
                home=tmp_path, persist=False,
            )
        assert isinstance(cfg, MaggyConfig)

    def test_populates_codebases(self, tmp_path: Path):
        from maggy.config import auto_configure
        dev = tmp_path / "dev"
        dev.mkdir()
        repo = dev / "webapp"
        repo.mkdir()
        (repo / ".git").mkdir()

        with patch("shutil.which", return_value=None):
            cfg = auto_configure(
                home=tmp_path, persist=False,
            )
        assert len(cfg.codebases) == 1
        assert cfg.codebases[0].key == "webapp"

    def test_persist_writes_file(self, tmp_path: Path):
        from maggy.config import auto_configure
        config_path = tmp_path / "config.yaml"
        with patch("shutil.which", return_value=None), \
             patch("maggy.config.CONFIG_DIR", tmp_path), \
             patch("maggy.config.CONFIG_PATH", config_path):
            cfg = auto_configure(
                home=tmp_path, persist=True,
            )
        assert config_path.exists()


# --- Relaxed is_configured ---


class TestIsConfiguredRelaxed:
    def test_false_without_anything(self, tmp_path: Path):
        from maggy.config import is_configured
        with patch("maggy.config.CONFIG_PATH", tmp_path / "nope.yaml"), \
             patch("maggy.config._CACHED", None), \
             patch("maggy.config._has_cli_history", return_value=False):
            result = is_configured()
        assert result is False

    def test_true_with_cli_history(self, tmp_path: Path):
        from maggy.config import is_configured
        with patch("maggy.config.CONFIG_PATH", tmp_path / "nope.yaml"), \
             patch("maggy.config._CACHED", None), \
             patch("maggy.config._has_cli_history", return_value=True):
            result = is_configured()
        assert result is True
