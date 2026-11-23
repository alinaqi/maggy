"""Tests for the root install.sh running against a clean HOME."""

from __future__ import annotations

import os
import pwd
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_SH = REPO_ROOT / "install.sh"
SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
# conftest redirects HOME, so "~" is a temp dir; the passwd entry is the real home.
REAL_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)


def _snapshot(path: Path) -> tuple[float, bytes] | None:
    """Record mtime and content of a real-HOME file, or None if absent."""
    if not path.exists():
        return None
    return path.stat().st_mtime, path.read_bytes()


def _run_install(home: Path) -> subprocess.CompletedProcess[str]:
    env = {"HOME": str(home), "PATH": SAFE_PATH, "LANG": "C"}
    return subprocess.run(
        ["bash", str(INSTALL_SH)],
        check=False,
        cwd=str(home),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


@pytest.fixture()
def clean_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    real = REAL_HOME.resolve()
    assert real not in home.resolve().parents and real != home.resolve()
    return home


def test_install_succeeds_on_empty_home(clean_home):
    result = _run_install(clean_home)
    assert result.returncode == 0, result.stderr[-2000:]


def test_install_records_bootstrap_dir(clean_home):
    _run_install(clean_home)
    marker = clean_home / ".claude" / ".bootstrap-dir"
    assert marker.read_text().strip() == str(REPO_ROOT)


def test_install_does_not_touch_real_home(clean_home):
    real_marker = REAL_HOME / ".claude" / ".bootstrap-dir"
    before = _snapshot(real_marker)
    _run_install(clean_home)
    assert _snapshot(real_marker) == before


def test_guard_uses_passwd_home_not_redirected_home():
    assert REAL_HOME != Path(os.path.expanduser("~"))
