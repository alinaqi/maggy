"""Tests for `maggy bootstrap` asset installation."""

from __future__ import annotations

import os

import pytest

from maggy.services.bootstrap import BootstrapError, run_bootstrap, _resolve_source


def _make_source(tmp_path):
    src = tmp_path / "bootstrap"
    (src / "skills" / "base").mkdir(parents=True)
    (src / "skills" / "base" / "SKILL.md").write_text("# base")
    (src / "commands").mkdir(parents=True)
    (src / "commands" / "maggy.md").write_text("# /maggy")
    (src / "hooks").mkdir(parents=True)
    (src / "hooks" / "route-task-hook").write_text("#!/bin/bash\n")
    (src / "bin").mkdir(parents=True)
    (src / "bin" / "deepseek").write_text("#!/usr/bin/env python3\n")
    (src / "plugins" / "demo").mkdir(parents=True)
    (src / "plugins" / "demo" / "plugin.yaml").write_text("id: demo\n")
    return src


def test_installs_all_asset_types(tmp_path):
    src = _make_source(tmp_path)
    home = tmp_path / "claude"
    bindir = tmp_path / "bin"
    plugdir = tmp_path / "plugins"
    result = run_bootstrap(src, claude_home=home, bin_dir=bindir, plugins_dir=plugdir)
    assert result == {"skills": 1, "commands": 1, "hooks": 1, "bin": 1, "plugins": 1}
    assert (home / "skills" / "base" / "SKILL.md").exists()
    assert (home / "commands" / "maggy.md").exists()
    assert (bindir / "deepseek").exists()
    assert (plugdir / "demo" / "plugin.yaml").exists()
    assert (home / ".bootstrap-dir").read_text() == str(src.resolve())


def test_bin_wrappers_are_executable(tmp_path):
    src = _make_source(tmp_path)
    bindir = tmp_path / "bin"
    run_bootstrap(src, claude_home=tmp_path / "c", bin_dir=bindir,
                  plugins_dir=tmp_path / "p")
    assert os.access(bindir / "deepseek", os.X_OK)


def test_idempotent(tmp_path):
    src = _make_source(tmp_path)
    args = dict(claude_home=tmp_path / "c", bin_dir=tmp_path / "b",
                plugins_dir=tmp_path / "p")
    run_bootstrap(src, **args)
    again = run_bootstrap(src, **args)  # no error on re-run
    assert again["skills"] == 1


def test_resolve_source_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MAGGY_BOOTSTRAP_DIR", str(tmp_path))
    assert _resolve_source(None) == tmp_path.resolve()


def test_no_source_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("MAGGY_BOOTSTRAP_DIR", raising=False)
    monkeypatch.setattr("maggy.services.bootstrap.Path.home", lambda: tmp_path)
    with pytest.raises(BootstrapError):
        _resolve_source(None)


def test_plugins_from_nested_maggy_dir(tmp_path):
    """Plugins under <root>/maggy/plugins (this repo's layout) are found."""
    src = tmp_path / "root"
    (src / "maggy" / "plugins" / "demo").mkdir(parents=True)
    (src / "maggy" / "plugins" / "demo" / "plugin.yaml").write_text("id: demo\n")
    (src / "maggy" / "plugins" / "__init__.py").write_text("")   # loader file
    (src / "maggy" / "plugins" / "manager.py").write_text("")    # loader file
    plug = tmp_path / "out"
    result = run_bootstrap(src, claude_home=tmp_path / "c",
                           bin_dir=tmp_path / "b", plugins_dir=plug)
    assert result["plugins"] == 1                       # the demo folder
    assert (plug / "demo" / "plugin.yaml").exists()
    assert not (plug / "__init__.py").exists()          # loader NOT copied
    assert not (plug / "manager.py").exists()
