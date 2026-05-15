"""Tests for mnemos CLI."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from maggy.mnemos.constants import MNEMOS_DIR


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "mnemos", *args],
        capture_output=True, text=True, cwd=str(cwd),
    )


class TestInit:
    def test_creates_mnemos_dir(self, mock_cwd: Path):
        r = _run(["init"], mock_cwd)
        assert r.returncode == 0
        assert (mock_cwd / MNEMOS_DIR).is_dir()
        assert (mock_cwd / MNEMOS_DIR / "mnemo.db").exists()

    def test_updates_gitignore(self, mock_cwd: Path):
        _run(["init"], mock_cwd)
        gi = mock_cwd / ".gitignore"
        assert gi.exists()
        assert ".mnemos/" in gi.read_text()

    def test_idempotent(self, mock_cwd: Path):
        _run(["init"], mock_cwd)
        r = _run(["init"], mock_cwd)
        assert r.returncode == 0
        assert "already" in r.stdout.lower()


class TestStatus:
    def test_status_after_init(self, mock_cwd: Path):
        _run(["init"], mock_cwd)
        r = _run(["status"], mock_cwd)
        assert r.returncode == 0
        assert "Nodes: 0" in r.stdout

    def test_status_no_init(self, mock_cwd: Path):
        r = _run(["status"], mock_cwd)
        assert r.returncode != 0


class TestFatigueCLI:
    def test_fatigue_after_init(self, mock_cwd: Path):
        _run(["init"], mock_cwd)
        r = _run(["fatigue"], mock_cwd)
        assert r.returncode == 0
        assert "not measured" in r.stdout.lower()


class TestCheckpointCLI:
    def test_checkpoint_force(self, mock_cwd: Path):
        _run(["init"], mock_cwd)
        r = _run(["checkpoint", "--force"], mock_cwd)
        assert r.returncode == 0
        assert "checkpoint" in r.stdout.lower()


class TestResumeCLI:
    def test_resume_no_checkpoint(self, mock_cwd: Path):
        _run(["init"], mock_cwd)
        r = _run(["resume"], mock_cwd)
        assert r.returncode == 0
        assert "no checkpoint" in r.stdout.lower()

    def test_resume_after_checkpoint(self, mock_cwd: Path):
        _run(["init"], mock_cwd)
        _run(["checkpoint", "--force"], mock_cwd)
        r = _run(["resume"], mock_cwd)
        assert r.returncode == 0
        assert "MNEMOS CHECKPOINT" in r.stdout
