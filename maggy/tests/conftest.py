"""Shared test fixtures for Maggy test suite."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

# -- Hermetic environment (must run before any maggy import) --
# Many maggy modules resolve ~/.maggy, ~/.claude and ~/bin at import time, so
# the throwaway HOME has to be in place before `from maggy...` below.

_PROVIDER_KEYS = (
    "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY",
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "XAI_API_KEY", "GROQ_API_KEY",
    "TOGETHER_API_KEY", "MOONSHOT_API_KEY", "KIMI_API_KEY",
    "OPENROUTER_API_KEY",
)


def _isolate_environment() -> str:
    """Point HOME at a temp dir, drop ~/bin from PATH, hide provider keys."""
    real_bin = str(Path.home() / "bin")
    home = tempfile.mkdtemp(prefix="maggy-test-home-")
    os.environ["HOME"] = home
    paths = os.environ.get("PATH", "").split(os.pathsep)
    os.environ["PATH"] = os.pathsep.join(p for p in paths if p != real_bin)
    for key in _PROVIDER_KEYS:
        os.environ.pop(key, None)
    return home


_TEST_HOME = _isolate_environment()


def pytest_unconfigure(config: pytest.Config) -> None:
    shutil.rmtree(_TEST_HOME, ignore_errors=True)


# Imported after _isolate_environment() on purpose (see above).
from maggy.config import (
    BudgetConfig,
    DashboardConfig,
    MaggyConfig,
    MeshConfig,
    RoutingConfig,
    StorageConfig,
)


@pytest.fixture
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def mock_cfg(tmp_path: Path) -> MaggyConfig:
    """Minimal MaggyConfig pointing to tmp storage."""
    return MaggyConfig(
        storage=StorageConfig(path=str(tmp_path / "store.db")),
        dashboard=DashboardConfig(),
        budget=BudgetConfig(daily_limit_usd=10.0),
        routing=RoutingConfig(),
        mesh=MeshConfig(),
    )


# -- Mnemos fixtures --


@pytest.fixture()
def tmp_mnemos_dir(tmp_path: Path) -> Path:
    """Create a temporary .mnemos directory."""
    mnemos = tmp_path / ".mnemos"
    mnemos.mkdir()
    return mnemos


@pytest.fixture()
def mock_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set CWD to a temp dir for init tests."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture()
def mock_transcript(tmp_path: Path) -> Path:
    """Create a fake transcript JSONL of known size."""
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_bytes(b"x" * 400_000)
    return transcript
