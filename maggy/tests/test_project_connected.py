"""Tests for project.connected event — auto-test on project open.

When a project is opened in Maggy (session create, auto-connect, preload),
the system emits a project.connected event. The e2e-testkit subscribes
and runs a lightweight regression scan in the background.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maggy.plugins.manager import HookBus, HookEvent, PluginManager

_PLUGIN_PATH = (
    Path(__file__).parent.parent
    / "plugins" / "e2e-testkit" / "plugin.py"
)


def _load_testkit_module():
    """Load the e2e-testkit plugin module for testing."""
    mod_name = "maggy_plugin_e2e_testkit"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, _PLUGIN_PATH)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = mod_name
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


_testkit_mod = _load_testkit_module()


class TestHookBusWiring:
    """Plugin manifest hooks get auto-wired to the bus."""

    def test_manifest_hooks_get_subscribed(self):
        bus = HookBus()
        pm = PluginManager(bus=bus)
        manifest = MagicMock()
        manifest.id = "test-plugin"
        manifest.hooks = [
            {"event": "project.connected", "fn": "on_connect"},
        ]
        manifest.heartbeat = []
        manifest.router = ""
        module = MagicMock()
        module.on_connect = AsyncMock()
        pm._wire_hooks(manifest, module)
        assert "project.connected" in bus._handlers
        assert len(bus._handlers["project.connected"]) == 1

    def test_missing_fn_skipped(self):
        bus = HookBus()
        pm = PluginManager(bus=bus)
        manifest = MagicMock()
        manifest.id = "test-plugin"
        manifest.hooks = [
            {"event": "project.connected", "fn": "nonexistent"},
        ]
        module = MagicMock(spec=[])
        pm._wire_hooks(manifest, module)
        assert "project.connected" not in bus._handlers


class TestProjectConnectedEmission:
    """Routes emit project.connected with correct payload."""

    @pytest.mark.asyncio
    async def test_emit_on_session_create(self):
        from maggy.api.routes_chat_sessions import _emit_project_connected
        pm = MagicMock()
        pm.emit = AsyncMock()
        await _emit_project_connected(
            pm, "my-project", "/tmp/my-project", "sess-001",
        )
        pm.emit.assert_called_once_with(
            "project.connected",
            {
                "project_key": "my-project",
                "working_dir": "/tmp/my-project",
                "session_id": "sess-001",
            },
        )

    @pytest.mark.asyncio
    async def test_emit_tolerates_no_plugin_manager(self):
        from maggy.api.routes_chat_sessions import _emit_project_connected
        await _emit_project_connected(None, "p", "/tmp", "s")


class TestTestkitHandler:
    """e2e-testkit on_project_connected handler."""

    @pytest.mark.asyncio
    async def test_handler_runs_regression_scan(self, tmp_path: Path):
        proj = tmp_path / "test-proj"
        proj.mkdir()
        (proj / "pyproject.toml").write_text("[project]\nname='test'\n")
        on_project_connected = _testkit_mod.on_project_connected
        with patch.object(
            _testkit_mod, "E2ETestKit",
        ) as MockKit:
            mock_kit = MagicMock()
            mock_kit.regression_scan.return_value = []
            MockKit.return_value = mock_kit
            await on_project_connected({
                "project_key": "test-proj",
                "working_dir": str(proj),
                "session_id": "s1",
            })
            MockKit.assert_called_once_with(str(proj))
            mock_kit.regression_scan.assert_called_once()

    @pytest.mark.asyncio
    async def test_handler_survives_missing_dir(self):
        on_project_connected = _testkit_mod.on_project_connected
        await on_project_connected({
            "project_key": "ghost",
            "working_dir": "/nonexistent/path",
            "session_id": "s1",
        })

    @pytest.mark.asyncio
    async def test_handler_survives_empty_payload(self):
        on_project_connected = _testkit_mod.on_project_connected
        await on_project_connected({})
