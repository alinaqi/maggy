"""Unit tests for the project_dir sandbox guard."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from maggy.api.project_guard import registered_roots, resolve_project_dir
from maggy.config import CodebaseConfig, MaggyConfig, ProjectConfig


def _cfg(*paths, codebase=None):
    projects = [
        ProjectConfig(name=f"p{i}", repo="o/r", path=str(p),
                      default_branch="main")
        for i, p in enumerate(paths)
    ]
    codebases = [CodebaseConfig(path=str(codebase), key="c")] if codebase else []
    return MaggyConfig(projects=projects, codebases=codebases)


def test_roots_are_realpaths(tmp_path):
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    assert registered_roots(_cfg(link)) == [real.resolve()]


def test_roots_include_codebases(tmp_path):
    assert registered_roots(_cfg(codebase=tmp_path)) == [tmp_path.resolve()]


def test_roots_skip_empty_paths():
    assert registered_roots(_cfg("")) == []


def test_resolve_inside_returns_realpath(tmp_path):
    assert resolve_project_dir(_cfg(tmp_path), str(tmp_path)) == str(
        tmp_path.resolve())


def test_resolve_outside_is_403(tmp_path):
    (tmp_path / "a").mkdir()
    with pytest.raises(HTTPException) as exc:
        resolve_project_dir(_cfg(tmp_path / "a"), str(tmp_path))
    assert exc.value.status_code == 403


def test_resolve_empty_is_400(tmp_path):
    with pytest.raises(HTTPException) as exc:
        resolve_project_dir(_cfg(tmp_path), "  ")
    assert exc.value.status_code == 400


def test_resolve_without_cfg_is_403(tmp_path):
    with pytest.raises(HTTPException) as exc:
        resolve_project_dir(None, str(tmp_path))
    assert exc.value.status_code == 403


def test_resolve_nonexistent_inside_is_400(tmp_path):
    with pytest.raises(HTTPException) as exc:
        resolve_project_dir(_cfg(tmp_path), str(tmp_path / "missing"))
    assert exc.value.status_code == 400


def test_dependency_reads_app_cfg(tmp_path):
    from maggy.api.project_guard import guarded_project_dir
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(cfg=_cfg(tmp_path))))
    assert guarded_project_dir(request, str(tmp_path)) == str(
        tmp_path.resolve())
