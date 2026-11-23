"""Shared fixtures for telos/e2e-testkit route security tests."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maggy.config import DashboardConfig, MaggyConfig, ProjectConfig

_PLUGINS = Path(__file__).resolve().parent.parent / "plugins"
KEY = "secret-key"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


telos = _load("telos_plugin", _PLUGINS / "telos" / "plugin.py")
testkit = _load(
    "maggy_plugin_e2e_testkit", _PLUGINS / "e2e-testkit" / "plugin.py",
)

ROUTES = [
    ("get", "/api/telos/status"),
    ("post", "/api/testkit/run"),
    ("post", "/api/testkit/drift"),
    ("post", "/api/testkit/intent"),
    ("get", "/api/testkit/history"),
]


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "registered"
    root.mkdir()
    (root / "pyproject.toml").write_text("[project]\nname='x'\n")
    return root


@pytest.fixture
def client(project, monkeypatch):
    app = FastAPI()
    app.state.cfg = MaggyConfig(
        dashboard=DashboardConfig(auth_mode="token", api_key=KEY),
        projects=[ProjectConfig(
            name="p", repo="o/p", path=str(project), default_branch="main",
        )],
    )
    app.include_router(telos.router)
    app.include_router(testkit.router)
    monkeypatch.setattr(testkit, "_kit", testkit.E2ETestKit(str(project)))
    return TestClient(app, headers={"X-API-Key": KEY})


@pytest.fixture
def spawn():
    with patch.object(subprocess, "run") as run, \
            patch.object(telos._scorer, "score_project") as score:
        run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        score.return_value = MagicMock(to_dict=lambda: {"ok": True})
        yield run, score


def call(client, route, project_dir):
    """Call (method, url) with project_dir using the client's headers."""
    method, url = route
    params = {"project_dir": str(project_dir)}
    return getattr(client, method)(url, params=params)
