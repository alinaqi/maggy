"""Skills and rules resolve in a pip/pipx install, not only in a source checkout."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

from harness_emitter_helpers import write

from maggy.harness.emitters.base import EmitterSources
from maggy.harness.emitters.sources import skill_source, sources_root

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MODULE = Path("maggy") / "harness" / "emitters" / "sources.py"


def _load_setup():
    spec = importlib.util.spec_from_file_location("maggy_setup", PACKAGE_ROOT / "setup.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_installed_layout_uses_the_bundled_library(tmp_path: Path) -> None:
    site = tmp_path / "venv" / "lib" / "python3.12" / "site-packages"
    module = write(site / MODULE, "")
    library = site / "maggy" / "harness" / "library"
    write(library / "skills" / "model-routing" / "SKILL.md", "---\nname: model-routing\n---\n")
    assert sources_root(module) == library
    assert "model-routing" in skill_source(EmitterSources(root=sources_root(module)), "model-routing")


def test_source_checkout_uses_the_repo_root(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    write(repo / "skills" / "x" / "SKILL.md", "x")
    write(repo / "rules" / "tdd.md", "x")
    assert sources_root(write(repo / "maggy" / MODULE, "")) == repo


def test_setup_bundles_repo_skills_and_rules_into_the_package(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    write(repo / "skills" / "python" / "SKILL.md", "py")
    write(repo / "rules" / "tdd.md", "tdd")
    package = tmp_path / "pkg" / "maggy"
    _load_setup().sync_library(repo, package)
    library = package / "harness" / "library"
    assert (library / "skills" / "python" / "SKILL.md").read_text() == "py"
    assert (library / "rules" / "tdd.md").read_text() == "tdd"


def test_setup_without_a_checkout_keeps_the_existing_library(tmp_path: Path) -> None:
    package = tmp_path / "sdist" / "maggy"
    kept = write(package / "harness" / "library" / "skills" / "a" / "SKILL.md", "a")
    _load_setup().sync_library(tmp_path / "no-repo", package)
    assert kept.read_text() == "a"


def test_wheel_package_data_ships_the_library() -> None:
    data = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text())
    globs = data["tool"]["setuptools"]["package-data"]["maggy"]
    assert "harness/library/**/*" in globs
