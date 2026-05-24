"""Tests for Plane 1 — Conformance (F1 = passed / total)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

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


_models = _load("telos_models", "models.py")
_conformance = _load("telos_conformance", "plane_conformance.py")
compute_f1 = _conformance.compute_f1
run_tests = _conformance.run_tests


class TestRunTests:

    def test_pytest_pass(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        (tmp_path / "test_ok.py").write_text(
            "def test_ok(): assert True\n"
        )
        result = run_tests(str(tmp_path))
        assert result["passed"] >= 1
        assert result["failed"] == 0

    def test_pytest_fail(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        (tmp_path / "test_fail.py").write_text(
            "def test_bad(): assert False\n"
        )
        result = run_tests(str(tmp_path))
        assert result["failed"] >= 1

    def test_no_tests_found(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        result = run_tests(str(tmp_path))
        assert result["passed"] == 0
        assert result["failed"] == 0

    def test_nonexistent_dir(self):
        result = run_tests("/nonexistent/path/xyz")
        assert result["error"] != ""


class TestComputeF1:

    def test_all_pass(self):
        r = {"passed": 10, "failed": 0, "error": ""}
        assert compute_f1(r) == pytest.approx(1.0)

    def test_all_fail(self):
        r = {"passed": 0, "failed": 5, "error": ""}
        assert compute_f1(r) == pytest.approx(0.0)

    def test_partial(self):
        r = {"passed": 7, "failed": 3, "error": ""}
        assert compute_f1(r) == pytest.approx(0.7)

    def test_no_tests_returns_one(self):
        r = {"passed": 0, "failed": 0, "error": ""}
        assert compute_f1(r) == pytest.approx(1.0)

    def test_error_returns_zero(self):
        r = {"passed": 0, "failed": 0, "error": "timeout"}
        assert compute_f1(r) == pytest.approx(0.0)
