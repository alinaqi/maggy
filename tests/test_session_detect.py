"""Tests for multi-CLI session detection."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from maggy.services.session_detect import (
    detect_all,
    detect_claude,
    detect_codex,
    detect_kimi,
)

_MOD = "maggy.services.session_detect._home"


def _patch_home(tmp_path):
    return patch(_MOD, return_value=tmp_path)


def test_detect_claude_from_history(tmp_path):
    """Finds Claude session by matching working dir."""
    hist = tmp_path / ".claude" / "history.jsonl"
    hist.parent.mkdir(parents=True)
    entry = {"project": "/tmp/proj", "sessionId": "c-123"}
    hist.write_text(json.dumps(entry) + "\n")
    with _patch_home(tmp_path):
        result = detect_claude("/tmp/proj")
    assert result is not None
    assert result.cli == "claude"
    assert result.session_id == "c-123"


def test_detect_claude_no_match(tmp_path):
    """Returns None when no matching dir in history."""
    hist = tmp_path / ".claude" / "history.jsonl"
    hist.parent.mkdir(parents=True)
    entry = {"project": "/other", "sessionId": "x"}
    hist.write_text(json.dumps(entry) + "\n")
    with _patch_home(tmp_path):
        assert detect_claude("/tmp/proj") is None


def test_detect_claude_missing_file():
    """Returns None when history.jsonl doesn't exist."""
    with _patch_home(Path("/nonexistent_detect_xyz")):
        assert detect_claude("/tmp/proj") is None


def test_detect_kimi_from_state(tmp_path):
    """Finds Kimi session from kimi.json work_dirs."""
    kimi_f = tmp_path / ".kimi" / "kimi.json"
    kimi_f.parent.mkdir(parents=True)
    data = {"work_dirs": [
        {"path": "/tmp/proj", "last_session_id": "k-1"},
    ]}
    kimi_f.write_text(json.dumps(data))
    with _patch_home(tmp_path):
        result = detect_kimi("/tmp/proj")
    assert result is not None
    assert result.cli == "kimi"
    assert result.session_id == "k-1"


def test_detect_kimi_null_session(tmp_path):
    """Returns None when last_session_id is null."""
    kimi_f = tmp_path / ".kimi" / "kimi.json"
    kimi_f.parent.mkdir(parents=True)
    data = {"work_dirs": [
        {"path": "/tmp/proj", "last_session_id": None},
    ]}
    kimi_f.write_text(json.dumps(data))
    with _patch_home(tmp_path):
        assert detect_kimi("/tmp/proj") is None


def test_detect_kimi_no_file():
    with _patch_home(Path("/nonexistent_detect_xyz")):
        assert detect_kimi("/tmp/proj") is None


def test_detect_codex_from_session(tmp_path):
    """Finds Codex session from rollout session file."""
    sess = tmp_path / ".codex" / "sessions" / "2026" / "05"
    sess.mkdir(parents=True)
    meta = {
        "type": "session_meta",
        "payload": {"id": "cx-1", "cwd": "/tmp/proj"},
    }
    (sess / "rollout-test.jsonl").write_text(
        json.dumps(meta) + "\n",
    )
    with _patch_home(tmp_path):
        result = detect_codex("/tmp/proj")
    assert result is not None
    assert result.cli == "codex"
    assert result.session_id == "cx-1"


def test_detect_codex_no_dir():
    with _patch_home(Path("/nonexistent_detect_xyz")):
        assert detect_codex("/tmp/proj") is None


def test_detect_all_aggregates(tmp_path):
    """detect_all gathers results from all CLIs."""
    hist = tmp_path / ".claude" / "history.jsonl"
    hist.parent.mkdir(parents=True)
    entry = {"project": "/tmp/p", "sessionId": "s1"}
    hist.write_text(json.dumps(entry) + "\n")
    with _patch_home(tmp_path):
        result = detect_all("/tmp/p")
    clis = [s.cli for s in result.sessions]
    assert "claude" in clis


def test_detect_all_empty(tmp_path):
    """detect_all returns empty when nothing found."""
    with _patch_home(tmp_path):
        result = detect_all("/tmp/p")
    assert result.sessions == []
