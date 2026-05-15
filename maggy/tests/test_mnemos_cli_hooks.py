"""Tests for hook dispatch handlers."""

import json
from pathlib import Path
from unittest.mock import patch

from maggy.mnemos.cli_hooks import (
    _hook_post_compact,
    _hook_pre_compact,
    _hook_session_start,
    emit_hook_output,
)
from maggy.mnemos.constants import JUST_COMPACTED_MARKER
from maggy.mnemos.db import MnemosDB


class TestEmitHookOutput:
    def test_outputs_json(self, capsys):
        emit_hook_output("hello")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["hookSpecificOutput"]["additionalContext"] == "hello"


class TestHookSessionStart:
    def test_no_checkpoint(self, tmp_mnemos_dir, capsys):
        db = MnemosDB(tmp_mnemos_dir)
        _hook_session_start({}, tmp_mnemos_dir, db)
        assert capsys.readouterr().out == ""

    def test_with_checkpoint(self, tmp_mnemos_dir, capsys):
        db = MnemosDB(tmp_mnemos_dir)
        from maggy.mnemos.checkpoint import write_checkpoint
        write_checkpoint(
            tmp_mnemos_dir, db, task_id="t",
            fatigue=0.5, force=True,
        )
        _hook_session_start({}, tmp_mnemos_dir, db)
        output = capsys.readouterr().out
        assert "hookSpecificOutput" in output


class TestHookPreCompact:
    def test_creates_marker(self, tmp_mnemos_dir, capsys):
        db = MnemosDB(tmp_mnemos_dir)
        _hook_pre_compact({}, tmp_mnemos_dir, db)
        marker = tmp_mnemos_dir / JUST_COMPACTED_MARKER
        assert marker.exists()


class TestHookPostCompact:
    def test_clears_marker(self, tmp_mnemos_dir, capsys):
        db = MnemosDB(tmp_mnemos_dir)
        from maggy.mnemos.checkpoint import write_checkpoint
        write_checkpoint(
            tmp_mnemos_dir, db, task_id="t",
            fatigue=0.8, force=True,
        )
        marker = tmp_mnemos_dir / JUST_COMPACTED_MARKER
        marker.write_text("test-id")
        _hook_post_compact({}, tmp_mnemos_dir, db)
        assert not marker.exists()

    def test_no_marker_noop(self, tmp_mnemos_dir, capsys):
        db = MnemosDB(tmp_mnemos_dir)
        _hook_post_compact({}, tmp_mnemos_dir, db)
        assert capsys.readouterr().out == ""
