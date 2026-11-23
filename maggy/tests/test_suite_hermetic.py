"""The test suite must not depend on the developer machine.

Guards for tests/conftest.py: HOME is a throwaway directory (so ~/.maggy,
~/.claude/council.yaml and ~/bin are never read), real provider API keys are
not visible, and pytest itself puts ../scripts on sys.path so no PYTHONPATH
is needed.
"""

from __future__ import annotations

import os
import pwd
import sys
import tempfile
from pathlib import Path

import pytest

_REAL_HOME = Path(pwd.getpwuid(os.getuid()).pw_dir)
_REPO_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def test_home_is_not_the_developer_home():
    assert Path.home() != _REAL_HOME
    assert Path(os.environ["HOME"]) != _REAL_HOME


def test_home_is_a_throwaway_temp_dir():
    home = Path.home()
    assert home.name.startswith("maggy-test-home-")
    assert home.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())


def test_developer_bin_dir_is_not_on_path():
    entries = [Path(p) for p in os.environ.get("PATH", "").split(os.pathsep)]
    assert _REAL_HOME / "bin" not in entries


@pytest.mark.parametrize("key", [
    "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY",
    "GEMINI_API_KEY", "XAI_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY",
])
def test_provider_api_keys_are_hidden(key):
    assert key not in os.environ


def test_pytest_config_puts_scripts_on_sys_path(request):
    configured = [
        Path(p).resolve() for p in request.config.getini("pythonpath")
    ]
    assert _REPO_SCRIPTS in configured
    assert str(_REPO_SCRIPTS) in [str(Path(p).resolve()) for p in sys.path]
