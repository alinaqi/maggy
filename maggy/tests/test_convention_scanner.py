"""Tests for project-specific convention detection from filesystem."""

from __future__ import annotations

from pathlib import Path

from maggy.routing_rules import Convention, RoutingRules
from maggy.services.convention_scanner import (
    ensure_scanned,
    scan_project,
)


def test_detects_supabase_migrations(tmp_path: Path):
    """supabase/migrations/ dir -> supabase convention."""
    (tmp_path / "supabase" / "migrations").mkdir(parents=True)
    convs = scan_project(str(tmp_path))
    texts = " ".join(c.text for c in convs)
    assert "supabase" in texts.lower()


def test_detects_alembic(tmp_path: Path):
    """alembic.ini -> alembic convention."""
    (tmp_path / "alembic.ini").write_text("[alembic]\n")
    convs = scan_project(str(tmp_path))
    texts = " ".join(c.text for c in convs)
    assert "alembic" in texts.lower()


def test_detects_npm(tmp_path: Path):
    """package-lock.json -> npm convention."""
    (tmp_path / "package-lock.json").write_text("{}")
    convs = scan_project(str(tmp_path))
    texts = " ".join(c.text for c in convs)
    assert "npm" in texts.lower()


def test_detects_pnpm(tmp_path: Path):
    """pnpm-lock.yaml -> pnpm convention."""
    (tmp_path / "pnpm-lock.yaml").write_text("")
    convs = scan_project(str(tmp_path))
    texts = " ".join(c.text for c in convs)
    assert "pnpm" in texts.lower()


def test_detects_pytest_in_pyproject(tmp_path: Path):
    """pyproject.toml with [tool.pytest] -> pytest convention."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['tests']\n"
    )
    convs = scan_project(str(tmp_path))
    texts = " ".join(c.text for c in convs)
    assert "pytest" in texts.lower()


def test_detects_ruff_in_pyproject(tmp_path: Path):
    """pyproject.toml with [tool.ruff] -> ruff convention."""
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length=88\n")
    convs = scan_project(str(tmp_path))
    texts = " ".join(c.text for c in convs)
    assert "ruff" in texts.lower()


def test_empty_dir_no_conventions(tmp_path: Path):
    """Empty directory produces no conventions."""
    convs = scan_project(str(tmp_path))
    assert convs == []


def test_all_conventions_have_auto_source(tmp_path: Path):
    """Detected conventions have source='auto-detected'."""
    (tmp_path / "Makefile").write_text("all:\n\techo hi\n")
    convs = scan_project(str(tmp_path))
    assert len(convs) >= 1
    assert all(c.source == "auto-detected" for c in convs)


def test_conventions_for_merges_project():
    """conventions_for includes project-specific conventions."""
    from maggy.routing_rules import conventions_for

    rules = RoutingRules(
        conventions=[Convention("Global rule", ["all"], "manual")],
        project_conventions={
            "protaige": [
                Convention("Use supabase db push", ["all"], "auto"),
            ],
        },
    )
    text = conventions_for(rules, "feature", "protaige")
    assert "Global rule" in text
    assert "supabase" in text


def test_conventions_for_without_project():
    """conventions_for without project_key returns only global."""
    from maggy.routing_rules import conventions_for

    rules = RoutingRules(
        conventions=[Convention("Global rule", ["all"], "manual")],
        project_conventions={
            "protaige": [
                Convention("Use supabase db push", ["all"], "auto"),
            ],
        },
    )
    text = conventions_for(rules, "feature")
    assert "Global rule" in text
    assert "supabase" not in text


def test_ensure_scanned_caches(tmp_path: Path):
    """ensure_scanned only scans once per project_key."""
    (tmp_path / "alembic.ini").write_text("[alembic]\n")
    rules = RoutingRules()
    ensure_scanned(rules, "my-proj", str(tmp_path))
    assert "my-proj" in rules.project_conventions
    count = len(rules.project_conventions["my-proj"])
    ensure_scanned(rules, "my-proj", str(tmp_path))
    assert len(rules.project_conventions["my-proj"]) == count


def test_yaml_roundtrip_project_conventions(tmp_path: Path):
    """Project conventions survive YAML save/load cycle."""
    from maggy.routing_rules_io import load, save

    rules = RoutingRules(
        project_conventions={
            "protaige": [
                Convention("Use supabase", ["all"], "auto-detected"),
            ],
            "edubites": [
                Convention("Use alembic", ["all"], "auto-detected"),
            ],
        },
    )
    yaml_path = tmp_path / "rules.yaml"
    save(rules, yaml_path)
    loaded = load(yaml_path)
    assert "protaige" in loaded.project_conventions
    assert "edubites" in loaded.project_conventions
    assert "supabase" in loaded.project_conventions["protaige"][0].text


def test_detects_docker_compose(tmp_path: Path):
    """docker-compose.yml -> docker convention."""
    (tmp_path / "docker-compose.yml").write_text("version: '3'\n")
    convs = scan_project(str(tmp_path))
    texts = " ".join(c.text for c in convs)
    assert "docker" in texts.lower()


def test_detects_github_actions(tmp_path: Path):
    """.github/workflows/ -> CI convention."""
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    convs = scan_project(str(tmp_path))
    texts = " ".join(c.text for c in convs)
    assert "github actions" in texts.lower()
