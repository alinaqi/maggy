"""Tests for startup bootstrap — auto-populate services."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _make_cfg(tmp_path: Path):
    """Build a minimal MaggyConfig with codebases."""
    from maggy.config import CodebaseConfig, MaggyConfig
    # Create fake codebase dirs
    repo_a = tmp_path / "repo-a"
    repo_a.mkdir()
    (repo_a / "main.py").write_text("print('hello')")
    (repo_a / "utils.ts").write_text("export const x = 1;")
    repo_b = tmp_path / "repo-b"
    repo_b.mkdir()
    (repo_b / "app.go").write_text("package main")
    return MaggyConfig(
        codebases=[
            CodebaseConfig(path=str(repo_a), key="repo-a"),
            CodebaseConfig(path=str(repo_b), key="repo-b"),
        ],
    )


class TestSeedCIKG:
    """Test CIKG seeding from codebases."""

    def test_creates_codebase_nodes(self, tmp_path):
        from maggy.main import _seed_cikg
        from maggy.cikg.graph import KnowledgeGraphService
        cfg = _make_cfg(tmp_path)
        cikg = KnowledgeGraphService(tmp_path / "cikg.db")
        _seed_cikg(cikg, cfg)
        nodes = cikg.list_nodes("codebase")
        assert len(nodes) == 2
        names = {n.name for n in nodes}
        assert names == {"repo-a", "repo-b"}

    def test_creates_language_nodes(self, tmp_path):
        from maggy.main import _seed_cikg
        from maggy.cikg.graph import KnowledgeGraphService
        cfg = _make_cfg(tmp_path)
        cikg = KnowledgeGraphService(tmp_path / "cikg.db")
        _seed_cikg(cikg, cfg)
        langs = cikg.list_nodes("technology")
        lang_names = {n.name for n in langs}
        assert "python" in lang_names
        assert "typescript" in lang_names
        assert "go" in lang_names

    def test_creates_edges(self, tmp_path):
        from maggy.main import _seed_cikg
        from maggy.cikg.graph import KnowledgeGraphService
        cfg = _make_cfg(tmp_path)
        cikg = KnowledgeGraphService(tmp_path / "cikg.db")
        _seed_cikg(cikg, cfg)
        edges = cikg.get_edges("codebase:repo-a", "out")
        edge_types = {e.edge_type for e in edges}
        assert "uses_technology" in edge_types

    def test_skips_missing_dirs(self, tmp_path):
        from maggy.config import CodebaseConfig, MaggyConfig
        from maggy.main import _seed_cikg
        from maggy.cikg.graph import KnowledgeGraphService
        cfg = MaggyConfig(codebases=[
            CodebaseConfig(path="/nonexistent/path", key="missing"),
        ])
        cikg = KnowledgeGraphService(tmp_path / "cikg.db")
        _seed_cikg(cikg, cfg)
        assert cikg.list_nodes("codebase") == []

    def test_idempotent(self, tmp_path):
        from maggy.main import _seed_cikg
        from maggy.cikg.graph import KnowledgeGraphService
        cfg = _make_cfg(tmp_path)
        cikg = KnowledgeGraphService(tmp_path / "cikg.db")
        _seed_cikg(cikg, cfg)
        _seed_cikg(cikg, cfg)  # run again
        nodes = cikg.list_nodes("codebase")
        assert len(nodes) == 2  # no duplicates


class TestBootstrap:
    """Test the full _bootstrap function."""

    @pytest.mark.asyncio
    async def test_calls_services(self):
        from maggy.main import _bootstrap
        app = MagicMock()
        app.state.history = MagicMock()
        app.state.introspector = MagicMock()
        app.state.cikg = None
        app.state.cfg = MagicMock()
        await _bootstrap(app)
        app.state.history.analyze.assert_called_once()
        app.state.introspector.analyze.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_missing_services(self):
        from maggy.main import _bootstrap
        app = MagicMock()
        app.state.history = None
        app.state.introspector = None
        app.state.cikg = None
        app.state.cfg = None
        await _bootstrap(app)  # should not raise

    @pytest.mark.asyncio
    async def test_handles_analyze_error(self):
        from maggy.main import _bootstrap
        app = MagicMock()
        app.state.history = MagicMock()
        app.state.history.analyze.side_effect = RuntimeError("db locked")
        app.state.introspector = None
        app.state.cikg = None
        app.state.cfg = None
        await _bootstrap(app)  # should not raise
