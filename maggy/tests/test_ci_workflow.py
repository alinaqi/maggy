"""The maggy test suite and ruff run in CI (.github/workflows/maggy-tests.yml)."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
import yaml

PKG_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = PKG_ROOT.parent / ".github" / "workflows" / "maggy-tests.yml"


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text())


def _steps(workflow: dict) -> list[dict]:
    jobs = list(workflow["jobs"].values())
    assert len(jobs) == 1
    return jobs[0]["steps"]


def _run_lines(workflow: dict) -> str:
    return "\n".join(step.get("run", "") for step in _steps(workflow))


def test_triggers_on_push_and_pull_request(workflow: dict) -> None:
    # PyYAML (YAML 1.1) parses the bare key `on` as boolean True.
    triggers = workflow.get("on", workflow.get(True))
    assert "push" in triggers
    assert "pull_request" in triggers


def test_uses_python_312(workflow: dict) -> None:
    setup = [s for s in _steps(workflow) if "setup-python" in s.get("uses", "")]
    assert setup and str(setup[0]["with"]["python-version"]) == "3.12"


def test_installs_maggy_editable_with_test_extra(workflow: dict) -> None:
    assert 'pip install -e "maggy[test]"' in _run_lines(workflow)


def test_runs_pytest_and_ruff(workflow: dict) -> None:
    runs = _run_lines(workflow)
    assert "cd maggy && python -m pytest tests -q" in runs
    assert "ruff check maggy/maggy" in runs


def test_is_hermetic(workflow: dict) -> None:
    text = WORKFLOW.read_text()
    assert "secrets." not in text
    assert workflow.get("permissions") == {"contents": "read"}


def test_test_extra_provides_runner_and_linter() -> None:
    project = tomllib.loads((PKG_ROOT / "pyproject.toml").read_text())
    extra = " ".join(project["project"]["optional-dependencies"]["test"])
    for dep in ("pytest", "pytest-asyncio", "ruff", "maggy-harness[review]"):
        assert dep in extra


def test_ruff_rules_are_pinned_in_pyproject() -> None:
    # Ruff's default rule set changes between versions; pin it so CI is stable.
    project = tomllib.loads((PKG_ROOT / "pyproject.toml").read_text())
    assert project["tool"]["ruff"]["lint"]["select"]
