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
    OrgConfig,
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
        org=OrgConfig(name="test-org"),
        storage=StorageConfig(path=str(tmp_path / "store.db")),
        dashboard=DashboardConfig(),
        budget=BudgetConfig(daily_limit_usd=10.0),
        routing=RoutingConfig(),
        mesh=MeshConfig(),
    )
