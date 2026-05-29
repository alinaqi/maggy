"""Shared test fixtures for Maggy test suite."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
