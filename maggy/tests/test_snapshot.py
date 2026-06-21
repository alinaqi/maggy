"""Tests for backup / restore / diff of the install footprint."""

from __future__ import annotations

import pytest

from maggy.services.snapshot import (
    collisions,
    create_backup,
    diff_install,
    list_backups,
    restore_backup,
)


def _make_source(root):
    """A fake bootstrap checkout."""
    src = root / "src"
    (src / "skills").mkdir(parents=True)
    (src / "skills" / "base.md").write_text("MAGGY base v2")
    (src / "commands").mkdir()
    (src / "commands" / "maggy.md").write_text("MAGGY cmd")
    (src / "hooks").mkdir()
    (src / "hooks" / "route-task-hook").write_text("MAGGY hook")
    (src / "bin").mkdir()
    (src / "bin" / "qwen3").write_text("MAGGY qwen")
    (src / "plugins" / "bip").mkdir(parents=True)
    (src / "plugins" / "bip" / "plugin.yaml").write_text("id: bip")
    return src


@pytest.fixture()
def homes(tmp_path):
    src = _make_source(tmp_path)
    ch, bd, pd, bk = (tmp_path / "claude", tmp_path / "bin",
                      tmp_path / "plugins", tmp_path / "backups")
    ch.mkdir()
    return src, ch, bd, pd, bk


class TestCollisions:
    def test_only_preexisting_are_collisions(self, homes):
        src, ch, bd, pd, _ = homes
        (ch / "skills").mkdir()
        (ch / "skills" / "base.md").write_text("MY OWN base")  # collides
        col = collisions(str(src), claude_home=ch, bin_dir=bd, plugins_dir=pd)
        assert col["skills"] == ["base.md"]
        assert col["bin"] == []  # qwen3 not installed yet -> no collision


class TestBackupRestore:
    def test_backup_captures_settings_and_collisions(self, homes):
        src, ch, bd, pd, bk = homes
        (ch / "settings.json").write_text('{"mine": true}')
        (ch / "skills").mkdir()
        (ch / "skills" / "base.md").write_text("MY OWN base")
        m = create_backup(str(src), claude_home=ch, bin_dir=bd, plugins_dir=pd,
                          backups_dir=bk, backup_id="b1")
        assert m["captured"]["settings"] == ["settings.json"]
        assert m["captured"]["skills"] == ["base.md"]
        assert (bk / "b1" / "claude" / "settings.json").exists()

    def test_restore_brings_back_original(self, homes):
        src, ch, bd, pd, bk = homes
        (ch / "settings.json").write_text('{"mine": true}')
        create_backup(str(src), claude_home=ch, bin_dir=bd, plugins_dir=pd,
                      backups_dir=bk, backup_id="b1")
        (ch / "settings.json").write_text('{"clobbered": true}')  # something changed it
        out = restore_backup("b1", claude_home=ch, bin_dir=bd, plugins_dir=pd, backups_dir=bk)
        assert out["restored"] >= 1
        assert (ch / "settings.json").read_text() == '{"mine": true}'

    def test_restore_latest_when_no_id(self, homes):
        src, ch, bd, pd, bk = homes
        (ch / "settings.json").write_text("v1")
        create_backup(str(src), claude_home=ch, backups_dir=bk, backup_id="20260101-000000")
        (ch / "settings.json").write_text("v2")
        create_backup(str(src), claude_home=ch, backups_dir=bk, backup_id="20260201-000000")
        (ch / "settings.json").write_text("v3")
        restore_backup(None, claude_home=ch, bin_dir=bd, plugins_dir=pd, backups_dir=bk)
        assert (ch / "settings.json").read_text() == "v2"  # newest backup

    def test_list_backups_newest_first(self, homes):
        src, ch, bd, pd, bk = homes
        create_backup(str(src), claude_home=ch, backups_dir=bk, backup_id="20260101-000000")
        create_backup(str(src), claude_home=ch, backups_dir=bk, backup_id="20260301-000000")
        ids = [b["id"] for b in list_backups(bk)]
        assert ids == ["20260301-000000", "20260101-000000"]

    def test_restore_missing_raises(self, homes):
        src, ch, bd, pd, bk = homes
        with pytest.raises(FileNotFoundError):
            restore_backup("nope", claude_home=ch, backups_dir=bk)


class TestDiff:
    def test_add_change_same(self, homes):
        src, ch, bd, pd, _ = homes
        (ch / "skills").mkdir()
        (ch / "skills" / "base.md").write_text("MAGGY base v2")  # identical -> same
        (ch / "commands").mkdir()
        (ch / "commands" / "maggy.md").write_text("OLD version")  # differs -> change
        d = diff_install(str(src), claude_home=ch, bin_dir=bd, plugins_dir=pd)
        assert d["skills"]["same"] == ["base.md"]
        assert d["commands"]["change"] == ["maggy.md"]
        assert "qwen3" in d["bin"]["add"]  # not installed -> would be added
