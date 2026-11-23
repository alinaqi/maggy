"""Shared fixtures for the Claude Code / Codex emitter tests."""

from __future__ import annotations

import os
from pathlib import Path

from maggy.harness.changes import FileChange
from maggy.harness.emitters import EmitterSources, Scope
from maggy.harness.schema import HarnessProfile

GOLDEN_DIR = Path(__file__).parent / "golden" / "harness"

SKILL = "---\nname: {name}\ndescription: {name} skill\n---\n\n# {name}\n\nUse {name} well.\n"


def fixture_profile(**overrides) -> HarnessProfile:
    data = {
        "instructions": {"include": ["rules/tdd.md", "rules/security.md"]},
        "skills": ["python", "react-web"],
        "hooks": {"after_edit": ["lint-changed"], "before_stop": ["run-focused-tests"],
                  "session_start": ["load-memory"]},
        "permissions": {"profiles": {"workspace": {
            "write": "workspace", "network": "registries", "shell": "allowlist"}}},
        "commands": {"test": "pytest -q", "lint": "ruff check ."},
        "worker": {"permission": "workspace"},
    }
    data.update(overrides)
    return HarnessProfile.model_validate(data)


def make_sources(tmp_path: Path) -> EmitterSources:
    root = tmp_path / "maggy-src"
    write(root / "rules" / "tdd.md", "## TDD\n\nWrite the failing test first.\n")
    write(root / "rules" / "security.md", "## Security\n\nNo secrets in code.\n")
    for name in ("python", "react-web", "go"):
        write(root / "skills" / name / "SKILL.md", SKILL.format(name=name))
    return EmitterSources(root=root)


def user_scope(tmp_path: Path) -> Scope:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return Scope(kind="user", root=home, home=home)


def project_scope(tmp_path: Path) -> Scope:
    repo = tmp_path / "repo"
    repo.mkdir(exist_ok=True)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return Scope(kind="project", root=repo, home=home)


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def serialize(changes: list[FileChange], tmp_path: Path) -> str:
    """Stable text of a plan: path, kind, status and the full new content."""
    parts = [f"=== {c.path} [{c.kind}/{c.status}]\n{c.after or ''}" for c in changes]
    return "\n".join(parts).replace(str(tmp_path), "<TMP>")


def assert_golden(name: str, text: str) -> None:
    path = GOLDEN_DIR / name
    if os.environ.get("UPDATE_GOLDEN") == "1":
        write(path, text)
    assert path.read_text() == text, f"golden mismatch: {name} (UPDATE_GOLDEN=1 to refresh)"


def by_name(changes: list[FileChange], suffix: str) -> FileChange:
    [found] = [c for c in changes if str(c.path).endswith(suffix)]
    return found
