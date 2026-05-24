"""Tests for project registry and project config parsing."""

from __future__ import annotations

from maggy.config import MaggyConfig, ProjectConfig, _from_dict
from maggy.registry import ProjectRegistry


class TestProjectConfigParsing:
    def test_from_dict_parses_projects(self):
        cfg = _from_dict({
            "projects": [
                {
                    "name": "alpha",
                    "repo": "acme/alpha",
                    "path": "~/code/alpha",
                    "default_branch": "main",
                },
                {
                    "name": "beta",
                    "repo": "acme/beta",
                    "path": "~/code/beta",
                    "default_branch": "develop",
                    "icpg": False,
                    "cikg": True,
                },
            ],
        })
        assert [project.name for project in cfg.projects] == ["alpha", "beta"]
        assert cfg.projects[0].icpg is True
        assert cfg.projects[0].cikg is False
        assert cfg.projects[1].default_branch == "develop"
        assert cfg.projects[1].icpg is False
        assert cfg.projects[1].cikg is True


class TestProjectRegistry:
    def test_registry_crud(self):
        alpha = ProjectConfig(
            name="alpha",
            repo="acme/alpha",
            path="/tmp/alpha",
            default_branch="main",
        )
        beta = ProjectConfig(
            name="beta",
            repo="acme/beta",
            path="/tmp/beta",
            default_branch="develop",
        )
        registry = ProjectRegistry(MaggyConfig(projects=[alpha]))
        assert registry.list() == [alpha]
        assert registry.get("alpha") == alpha
        registry.add(beta)
        assert registry.get("beta") == beta
        assert registry.remove("alpha") is True
        assert registry.get("alpha") is None
        assert registry.remove("alpha") is False

    def test_add_duplicate_raises(self):
        import pytest
        alpha = ProjectConfig(
            name="alpha",
            repo="acme/alpha",
            path="/tmp/alpha",
            default_branch="main",
        )
        registry = ProjectRegistry(MaggyConfig(projects=[alpha]))
        with pytest.raises(ValueError, match="already exists"):
            registry.add(alpha)


class TestOpenFolder:
    def _make_client(self, registry):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from maggy.api.routes_projects import router
        app = FastAPI()
        app.include_router(router)
        app.state.registry = registry
        app.state.cfg = MaggyConfig()
        return TestClient(app)

    def test_open_existing_dir(self, tmp_path):
        registry = ProjectRegistry(MaggyConfig())
        client = self._make_client(registry)
        r = client.post("/api/projects/open-folder", json={"path": str(tmp_path)})
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == tmp_path.name
        assert data["status"] == "registered"
        assert registry.get(tmp_path.name) is not None

    def test_open_nonexistent_dir(self):
        registry = ProjectRegistry(MaggyConfig())
        client = self._make_client(registry)
        r = client.post("/api/projects/open-folder", json={"path": "/nonexistent/path/xyz"})
        assert r.status_code == 400

    def test_open_already_registered(self, tmp_path):
        p = ProjectConfig(name=tmp_path.name, repo="local/x", path=str(tmp_path), default_branch="main")
        registry = ProjectRegistry(MaggyConfig(projects=[p]))
        client = self._make_client(registry)
        r = client.post("/api/projects/open-folder", json={"path": str(tmp_path)})
        assert r.status_code == 201
        assert r.json()["status"] == "already_registered"

    def test_open_with_tilde(self, tmp_path):
        registry = ProjectRegistry(MaggyConfig())
        client = self._make_client(registry)
        r = client.post("/api/projects/open-folder", json={"path": str(tmp_path)})
        assert r.status_code == 201
