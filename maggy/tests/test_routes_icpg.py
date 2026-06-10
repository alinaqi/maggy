"""Tests for /api/icpg/{key}/build auto-build endpoint."""

from __future__ import annotations

import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maggy.api import routes_icpg
from maggy.config import CodebaseConfig


def _app(mock_cfg):
    app = FastAPI()
    app.state.cfg = mock_cfg
    app.include_router(routes_icpg.router)
    return app


@pytest.fixture
def git_codebase(mock_cfg, tmp_path):
    """A configured codebase whose path is a git repo."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    mock_cfg.codebases = [CodebaseConfig(path=str(repo), key="demo")]
    return mock_cfg


@pytest.fixture(autouse=True)
def _clear_inflight():
    routes_icpg._BUILDS_IN_FLIGHT.clear()
    yield
    routes_icpg._BUILDS_IN_FLIGHT.clear()


def test_build_unknown_project(mock_cfg):
    client = TestClient(_app(mock_cfg))
    resp = client.post("/api/icpg/nope/build")
    assert resp.status_code == 200
    assert "Unknown project" in resp.json()["error"]


def test_build_rejects_non_git(mock_cfg, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    mock_cfg.codebases = [CodebaseConfig(path=str(plain), key="demo")]
    client = TestClient(_app(mock_cfg))
    resp = client.post("/api/icpg/demo/build")
    assert "Not a git repository" in resp.json()["error"]


def test_build_success_returns_stats(git_codebase, monkeypatch):
    monkeypatch.setattr(
        routes_icpg, "_run_bootstrap",
        lambda path, days: subprocess.CompletedProcess([], 0, "done", ""),
    )
    monkeypatch.setattr(routes_icpg, "_resolve_db", lambda cfg, key: "/x/reason.db")
    monkeypatch.setattr(
        routes_icpg, "_stats",
        lambda db: {"reasons": 3, "symbols": 9, "edges": 12, "drift": 0},
    )
    client = TestClient(_app(git_codebase))
    resp = client.post("/api/icpg/demo/build")
    body = resp.json()
    assert body["ok"] is True
    assert body["stats"]["reasons"] == 3


def test_build_propagates_cli_failure(git_codebase, monkeypatch):
    monkeypatch.setattr(
        routes_icpg, "_run_bootstrap",
        lambda path, days: subprocess.CompletedProcess([], 1, "", "boom"),
    )
    client = TestClient(_app(git_codebase))
    resp = client.post("/api/icpg/demo/build")
    assert "boom" in resp.json()["error"]


def test_build_rejects_concurrent(git_codebase, monkeypatch):
    monkeypatch.setattr(routes_icpg, "_run_bootstrap",
                        lambda path, days: subprocess.CompletedProcess([], 0, "", ""))
    routes_icpg._BUILDS_IN_FLIGHT.add("demo")
    client = TestClient(_app(git_codebase))
    resp = client.post("/api/icpg/demo/build")
    assert "already running" in resp.json()["error"]


def test_build_clears_inflight_after_success(git_codebase, monkeypatch):
    monkeypatch.setattr(routes_icpg, "_run_bootstrap",
                        lambda path, days: subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(routes_icpg, "_resolve_db", lambda cfg, key: None)
    client = TestClient(_app(git_codebase))
    client.post("/api/icpg/demo/build")
    assert "demo" not in routes_icpg._BUILDS_IN_FLIGHT
