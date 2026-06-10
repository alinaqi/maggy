"""Tests for /api/skills routes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from maggy.api.routes_skills import router
from maggy.skills.registry import SkillRegistry

SKILL_TEMPLATE = """\
---
name: {name}
description: {name} skill
when-to-use: Always
effort: medium
---

# {name}

Content for {name}.

```python
x = 1
```
"""


def _make_skill(base: Path, name: str) -> None:
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(SKILL_TEMPLATE.format(name=name))


@pytest.fixture()
def app_with_skills(tmp_path: Path) -> FastAPI:
    global_dir = tmp_path / "global"
    global_dir.mkdir()
    _make_skill(global_dir, "base")
    _make_skill(global_dir, "python")
    _make_skill(global_dir, "security")

    proj_dir = tmp_path / "project" / ".claude" / "skills"
    proj_dir.mkdir(parents=True)
    _make_skill(proj_dir, "python")
    _make_skill(proj_dir, "custom-api")

    app = FastAPI()
    app.include_router(router)
    reg = SkillRegistry(global_dir=global_dir)
    reg.load_global()
    reg.load_project("test-proj", str(tmp_path / "project"))
    app.state.skills = reg
    app.state.auth_key = None
    return app


@pytest.fixture()
def client(app_with_skills: FastAPI) -> TestClient:
    return TestClient(app_with_skills)


class TestListSkills:
    def test_list_all(self, client: TestClient):
        r = client.get("/api/skills")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert data["global_count"] == 3

    def test_list_with_project(self, client: TestClient):
        r = client.get("/api/skills?project_key=test-proj")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 4
        assert data["project_count"] == 2


class TestGetSkill:
    def test_get_existing(self, client: TestClient):
        r = client.get("/api/skills/base")
        assert r.status_code == 200
        data = r.json()
        assert data["metadata"]["name"] == "base"
        assert "Content for base" in data["content"]

    def test_get_missing(self, client: TestClient):
        r = client.get("/api/skills/nonexistent")
        assert r.status_code == 404

    def test_get_project_override(self, client: TestClient):
        r = client.get("/api/skills/python?project_key=test-proj")
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "project"


class TestListGlobal:
    def test_global_only(self, client: TestClient):
        r = client.get("/api/skills/global")
        assert r.status_code == 200
        data = r.json()
        assert len(data["skills"]) == 3


class TestListProject:
    def test_project_skills(self, client: TestClient):
        r = client.get("/api/skills/project/test-proj")
        assert r.status_code == 200
        data = r.json()
        assert len(data["skills"]) == 2

    def test_unknown_project(self, client: TestClient):
        r = client.get("/api/skills/project/unknown")
        assert r.status_code == 200
        data = r.json()
        assert len(data["skills"]) == 0


class TestValidate:
    def test_validate_by_content(self, client: TestClient):
        r = client.post("/api/skills/validate", json={
            "name": "test-skill",
            "content": SKILL_TEMPLATE.format(name="test-skill"),
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_valid"] is True

    def test_validate_invalid(self, client: TestClient):
        r = client.post("/api/skills/validate", json={
            "name": "bad",
            "content": "No frontmatter here",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_valid"] is False


class TestValidateAll:
    def test_validates_all_global(self, client: TestClient):
        r = client.post("/api/skills/validate-all")
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) == 3


class TestReload:
    def test_reload(self, client: TestClient):
        r = client.post("/api/skills/reload")
        assert r.status_code == 200
        data = r.json()
        assert data["count"] >= 3
