"""Declarative filesystem scanner for project-specific conventions.

Scans a project directory for config files, lock files, and directory
structures to auto-detect tooling conventions (e.g. supabase vs alembic,
npm vs pnpm, pytest vs jest).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maggy.routing_rules import Convention, RoutingRules


@dataclass
class ScanRule:
    """A filesystem marker that implies a convention."""

    marker: str
    convention: str
    applies_to: list[str] = field(default_factory=lambda: ["all"])
    content_match: str = ""
    is_dir: bool = False


RULES: list[ScanRule] = [
    ScanRule(
        "supabase/migrations", is_dir=True,
        convention="Use `supabase db push` for migrations. RLS policies required.",
    ),
    ScanRule(
        "alembic.ini",
        convention="Use `alembic revision --autogenerate` for schema changes.",
    ),
    ScanRule(
        "package-lock.json",
        convention="Package manager: npm. Use `npm install`, not yarn/pnpm.",
    ),
    ScanRule(
        "pnpm-lock.yaml",
        convention="Package manager: pnpm. Use `pnpm install`, not npm/yarn.",
    ),
    ScanRule(
        "yarn.lock",
        convention="Package manager: yarn. Use `yarn add`, not npm/pnpm.",
    ),
    ScanRule(
        "pyproject.toml", content_match=r"\[tool\.ruff\]",
        convention="Linter: ruff. Run `ruff check .` before committing.",
    ),
    ScanRule(
        "pyproject.toml", content_match=r"\[tool\.pytest",
        convention="Testing: pytest. Run `pytest` for tests.",
        applies_to=["feature", "bug", "all"],
    ),
    ScanRule(
        "pytest.ini",
        convention="Testing: pytest. Run `pytest` for tests.",
        applies_to=["feature", "bug", "all"],
    ),
    ScanRule(
        "docker-compose.yml",
        convention="Use Docker Compose for local services. `docker compose up -d`.",
    ),
    ScanRule(
        ".github/workflows", is_dir=True,
        convention="CI: GitHub Actions. Check workflow status before merging.",
    ),
    ScanRule(
        "Makefile",
        convention="Project uses Make. Check `make help` for available targets.",
    ),
    ScanRule(
        "tailwind.config.js",
        convention="Styling: Tailwind CSS. Use utility classes, not custom CSS.",
        applies_to=["feature"],
    ),
    ScanRule(
        "tailwind.config.ts",
        convention="Styling: Tailwind CSS. Use utility classes, not custom CSS.",
        applies_to=["feature"],
    ),
]


def scan_project(working_dir: str) -> list[Convention]:
    """Scan project directory, return detected conventions."""
    from maggy.routing_rules import Convention as Conv

    root = Path(working_dir)
    found: list[Conv] = []
    seen: set[str] = set()
    for rule in RULES:
        if not _matches(root, rule):
            continue
        if rule.convention in seen:
            continue
        seen.add(rule.convention)
        found.append(Conv(rule.convention, list(rule.applies_to), "auto-detected"))
    return found


def ensure_scanned(
    rules: RoutingRules, project_key: str, working_dir: str,
) -> None:
    """Scan project if not already cached in rules."""
    if project_key in rules.project_conventions:
        return
    convs = scan_project(working_dir)
    rules.project_conventions[project_key] = convs


def _matches(root: Path, rule: ScanRule) -> bool:
    """Check if a scan rule matches the project directory."""
    target = root / rule.marker
    if rule.is_dir:
        return target.is_dir()
    if not target.is_file():
        return False
    if not rule.content_match:
        return True
    try:
        text = target.read_text(errors="ignore")[:4096]
        return bool(re.search(rule.content_match, text))
    except OSError:
        return False
