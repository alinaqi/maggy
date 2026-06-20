"""Tests for `maggy uninstall` — symmetric, non-destructive asset removal."""

from __future__ import annotations

import pytest

from maggy.services.bootstrap import BootstrapError, run_bootstrap
from maggy.services.uninstall import plan_uninstall, run_uninstall


def _make_source(root):
    """A fake bootstrap checkout: skills/ commands/ hooks/ bin/ plugins/."""
    src = root / "src"
    (src / "skills").mkdir(parents=True)
    (src / "skills" / "base.md").write_text("base")
    (src / "skills" / "python").mkdir()
    (src / "skills" / "python" / "SKILL.md").write_text("py")
    (src / "commands").mkdir()
    (src / "commands" / "maggy.md").write_text("cmd")
    (src / "hooks").mkdir()
    (src / "hooks" / "route-task-hook").write_text("hook")
    (src / "bin").mkdir()
    (src / "bin" / "qwen3").write_text("#!/bin/sh\n")
    (src / "plugins" / "build-in-public").mkdir(parents=True)
    (src / "plugins" / "build-in-public" / "plugin.yaml").write_text("id: bip")
    return src


@pytest.fixture()
def installed(tmp_path):
    src = _make_source(tmp_path)
    ch, bd, pd = tmp_path / "claude", tmp_path / "bin", tmp_path / "plugins"
    run_bootstrap(str(src), claude_home=ch, bin_dir=bd, plugins_dir=pd)
    return src, ch, bd, pd


class TestPlan:
    def test_plan_lists_installed_assets(self, installed):
        src, ch, bd, pd = installed
        plan = plan_uninstall(str(src), claude_home=ch, bin_dir=bd, plugins_dir=pd)
        assert "base.md" in plan["skills"] and "python" in plan["skills"]
        assert "qwen3" in plan["bin"]
        assert "build-in-public" in plan["plugins"]

    def test_plan_is_nondestructive(self, installed):
        src, ch, bd, pd = installed
        plan_uninstall(str(src), claude_home=ch, bin_dir=bd, plugins_dir=pd)
        assert (ch / "skills" / "base.md").exists()  # preview removed nothing


class TestRun:
    def test_removes_installed_assets(self, installed):
        src, ch, bd, pd = installed
        run_uninstall(str(src), claude_home=ch, bin_dir=bd, plugins_dir=pd)
        assert not (ch / "skills" / "base.md").exists()
        assert not (ch / "skills" / "python").exists()
        assert not (ch / "commands" / "maggy.md").exists()
        assert not (bd / "qwen3").exists()
        assert not (pd / "build-in-public").exists()

    def test_spares_user_files(self, installed):
        src, ch, bd, pd = installed
        (ch / "skills" / "my-own.md").write_text("keep")  # user's own asset
        (bd / "my-tool").write_text("keep")
        run_uninstall(str(src), claude_home=ch, bin_dir=bd, plugins_dir=pd)
        assert (ch / "skills" / "my-own.md").exists()
        assert (bd / "my-tool").exists()

    def test_removes_marker(self, installed):
        src, ch, bd, pd = installed
        assert (ch / ".bootstrap-dir").exists()
        run_uninstall(str(src), claude_home=ch, bin_dir=bd, plugins_dir=pd)
        assert not (ch / ".bootstrap-dir").exists()

    def test_no_source_raises(self, tmp_path, monkeypatch):
        monkeypatch.delenv("MAGGY_BOOTSTRAP_DIR", raising=False)
        # point HOME at an empty dir so no marker is found
        monkeypatch.setenv("HOME", str(tmp_path / "empty_home"))
        with pytest.raises(BootstrapError):
            run_uninstall(None)
