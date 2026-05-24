"""Tests for IFS Scorer — combines F1 × F2 × F3."""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

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
_scorer = _load("telos_ifs_scorer", "ifs_scorer.py")
score_project = _scorer.score_project
IFSScore = sys.modules["telos_models"].IFSScore


@pytest.fixture()
def project_with_cortex(tmp_path):
    """Project with tests, cortex DB, and reasons."""
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    (tmp_path / "test_ok.py").write_text(
        "def test_ok(): assert True\n"
    )
    db_path = tmp_path / ".cortex" / "cortex.db"
    db_path.parent.mkdir()
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE reasons (
            id TEXT PRIMARY KEY, goal TEXT,
            decision_type TEXT DEFAULT 'task',
            scope TEXT DEFAULT '[]', owner TEXT,
            status TEXT DEFAULT 'proposed',
            preconditions TEXT DEFAULT '[]',
            postconditions TEXT DEFAULT '[]',
            invariants TEXT DEFAULT '[]',
            anti_criteria TEXT DEFAULT '[]',
            parent_id TEXT, created_at TEXT,
            fulfilled_at TEXT
        );
        CREATE TABLE drift_events (
            id TEXT PRIMARY KEY, symbol_id TEXT,
            from_reason_id TEXT, severity REAL,
            resolved INTEGER DEFAULT 0,
            detected_at TEXT
        );
        CREATE TABLE symbols (
            id TEXT PRIMARY KEY, name TEXT,
            file_path TEXT, symbol_type TEXT,
            language TEXT, created_at TEXT
        );
        CREATE TABLE edges (
            id TEXT PRIMARY KEY, from_id TEXT,
            to_id TEXT, edge_type TEXT,
            created_at TEXT
        );
    """)
    conn.execute(
        "INSERT INTO reasons VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("R-1", "Auth", "task", '[]', "alice",
         "fulfilled", '["db"]', '["ok"]', '[]',
         '[]', None, "2026-01-01", "2026-01-05"),
    )
    conn.commit()
    conn.close()
    return tmp_path


class TestScoreProject:

    def test_with_cortex(self, project_with_cortex):
        result = score_project(str(project_with_cortex))
        assert isinstance(result.ifs, IFSScore)
        assert result.ifs.f1 == pytest.approx(1.0)
        assert result.ifs.f2 == pytest.approx(1.0)
        assert result.ifs.composite > 0

    def test_without_cortex(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        (tmp_path / "test_ok.py").write_text(
            "def test_ok(): assert True\n"
        )
        result = score_project(str(tmp_path))
        assert result.ifs.f2 == pytest.approx(1.0)
        assert result.ifs.f3 == pytest.approx(1.0)
        assert result.ifs.composite == pytest.approx(
            result.ifs.f1,
        )

    def test_result_has_project_name(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        result = score_project(str(tmp_path))
        assert result.project == tmp_path.name
