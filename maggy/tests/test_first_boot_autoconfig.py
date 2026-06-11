"""Tests for zero-config first-boot auto-configuration."""

from __future__ import annotations

from unittest.mock import patch

import maggy.config as c
from maggy.config import (
    CodebaseConfig,
    MaggyConfig,
    is_placeholder,
)


def _placeholder_cfg() -> MaggyConfig:
    cfg = MaggyConfig()
    cfg.issue_tracker.github.org = "your-org"
    cfg.issue_tracker.github.repos = ["your-org/api"]
    cfg.codebases = [CodebaseConfig(path="~/dev/your-org/api", key="api")]
    return cfg


def test_detects_placeholder_template():
    assert is_placeholder(_placeholder_cfg()) is True


def test_real_config_is_not_placeholder():
    cfg = MaggyConfig(codebases=[CodebaseConfig(path="/home/me/proj", key="proj")])
    cfg.issue_tracker.github.org = "acme"
    cfg.issue_tracker.github.repos = ["acme/api"]
    assert is_placeholder(cfg) is False


def test_empty_config_is_not_placeholder():
    assert is_placeholder(MaggyConfig()) is False


def test_bootstrap_runs_autoconfig_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "CONFIG_PATH", tmp_path / "nope.yaml")
    real = MaggyConfig(codebases=[CodebaseConfig(path="/x", key="x")])
    with patch.object(c, "auto_configure", return_value=real) as ac:
        out = c.load_or_bootstrap(refresh=True)
    ac.assert_called_once()
    assert out is real


def test_bootstrap_runs_autoconfig_on_placeholder(tmp_path, monkeypatch):
    p = tmp_path / "config.yaml"
    monkeypatch.setattr(c, "CONFIG_PATH", p)
    c.save(_placeholder_cfg())
    real = MaggyConfig(codebases=[CodebaseConfig(path="/x", key="x")])
    with patch.object(c, "auto_configure", return_value=real) as ac:
        out = c.load_or_bootstrap(refresh=True)
    ac.assert_called_once()
    assert out is real


def test_bootstrap_keeps_real_config(tmp_path, monkeypatch):
    p = tmp_path / "config.yaml"
    monkeypatch.setattr(c, "CONFIG_PATH", p)
    real = MaggyConfig(codebases=[CodebaseConfig(path="/home/me/proj", key="proj")])
    real.issue_tracker.github.org = "acme"
    c.save(real)
    with patch.object(c, "auto_configure") as ac:
        out = c.load_or_bootstrap(refresh=True)
    ac.assert_not_called()
    assert out.codebases[0].key == "proj"


def test_bootstrap_falls_back_to_empty_on_discovery_error(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "CONFIG_PATH", tmp_path / "nope.yaml")
    with patch.object(c, "auto_configure", side_effect=RuntimeError("boom")):
        out = c.load_or_bootstrap(refresh=True)
    assert is_placeholder(out) is False  # clean empty config, no fake repos
