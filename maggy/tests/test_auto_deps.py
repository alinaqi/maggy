"""Tests for automatic dependency installation."""

from __future__ import annotations

import types
from unittest.mock import patch, call

import pytest

from maggy.services import auto_deps
from maggy.services.auto_deps import ensure_import

_PIP = "maggy.services.auto_deps._pip_install"


class TestEnsureImport:
    """Auto-install missing packages on demand."""

    def test_already_installed_returns_module(self):
        mod = ensure_import("json")
        assert hasattr(mod, "dumps")

    def test_missing_triggers_pip_then_imports(self):
        fake_mod = types.ModuleType("fake_xyz")
        installed = []

        def fake_pip(name):
            installed.append(name)

        original = auto_deps.importlib.import_module

        def patched(name):
            if name == "fake_xyz" and not installed:
                raise ImportError("missing")
            if name == "fake_xyz":
                return fake_mod
            return original(name)

        with patch.object(
            auto_deps.importlib, "import_module", patched,
        ), patch(_PIP, side_effect=fake_pip):
            result = ensure_import("fake_xyz")

        assert result is fake_mod
        assert installed == ["fake_xyz"]

    def test_custom_pip_name_used(self):
        fake_mod = types.ModuleType("docx")
        installed = []

        def fake_pip(name):
            installed.append(name)

        original = auto_deps.importlib.import_module

        def patched(name):
            if name == "docx" and not installed:
                raise ImportError("missing")
            if name == "docx":
                return fake_mod
            return original(name)

        with patch.object(
            auto_deps.importlib, "import_module", patched,
        ), patch(_PIP, side_effect=fake_pip):
            ensure_import("docx", pip_name="python-docx")

        assert installed == ["python-docx"]

    def test_install_failure_raises(self):
        original = auto_deps.importlib.import_module

        def patched(name):
            if name == "nope_pkg":
                raise ImportError("nope")
            return original(name)

        with patch.object(
            auto_deps.importlib, "import_module", patched,
        ), patch(
            _PIP, side_effect=RuntimeError("pip failed"),
        ):
            with pytest.raises(RuntimeError, match="pip failed"):
                ensure_import("nope_pkg")

    def test_pip_install_uses_quiet_flag(self):
        with patch(
            "maggy.services.auto_deps.subprocess.check_call",
        ) as mock_call:
            auto_deps._pip_install("some-pkg")

        cmd = mock_call.call_args[0][0]
        assert "-q" in cmd
        assert "some-pkg" in cmd
