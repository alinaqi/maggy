"""Integration tests for Telos plugin — registration + routes."""

from __future__ import annotations

import asyncio
import importlib.util
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

_TELOS_DIR = (
    Path(__file__).resolve().parent.parent / "plugins" / "telos"
)


def _load(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    path = _TELOS_DIR / filename
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_load("telos_models", "models.py")
_load("cortex_reader", "cortex_reader.py")
_load("telos_conformance", "plane_conformance.py")
_load("telos_validation", "plane_validation.py")
_load("telos_integrity", "plane_integrity.py")
_load("telos_ifs_scorer", "ifs_scorer.py")


class TestPluginRegistration:

    def test_register_sets_up(self):
        plugin = _load("telos_plugin", "plugin.py")
        bus = MagicMock()
        manifest = MagicMock()
        plugin.register(bus, manifest)
        assert plugin.router is not None

    def test_has_router_prefix(self):
        plugin = _load("telos_plugin", "plugin.py")
        assert plugin.router.prefix == "/api/telos"


class TestOnProjectConnected:

    @pytest.mark.asyncio
    async def test_runs_on_connect(self, tmp_path):
        plugin = _load("telos_plugin", "plugin.py")
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        (tmp_path / "test_ok.py").write_text(
            "def test_ok(): assert True\n"
        )
        payload = {
            "working_dir": str(tmp_path),
            "project_key": "test-proj",
        }
        await plugin.on_project_connected(payload)

    @pytest.mark.asyncio
    async def test_survives_empty_payload(self):
        plugin = _load("telos_plugin", "plugin.py")
        await plugin.on_project_connected({})

    @pytest.mark.asyncio
    async def test_survives_missing_dir(self):
        plugin = _load("telos_plugin", "plugin.py")
        await plugin.on_project_connected({
            "working_dir": "/nonexistent/xyz",
            "project_key": "nope",
        })


class TestPluginYaml:

    def test_manifest_exists(self):
        yaml_path = _TELOS_DIR / "plugin.yaml"
        assert yaml_path.exists()

    def test_manifest_has_hooks(self):
        import yaml
        yaml_path = _TELOS_DIR / "plugin.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        assert "hooks" in data
        events = [h["event"] for h in data["hooks"]]
        assert "project.connected" in events

    def test_manifest_id_is_telos(self):
        import yaml
        yaml_path = _TELOS_DIR / "plugin.yaml"
        data = yaml.safe_load(yaml_path.read_text())
        assert data["id"] == "telos"
