"""`maggy harness init` gives every agent the generic engineering rules by default."""

from __future__ import annotations

from pathlib import Path

import yaml
from harness_cli_helpers import TESTED, FakeTools, invoke, make_env

BASE_RULES = ["rules/tdd-workflow.md", "rules/quality-gates.md", "rules/security.md", "rules/changelog.md"]


def _init(tmp_path: Path, extra: list[str]) -> dict:
    env = make_env(tmp_path, FakeTools({"claude": TESTED["claude"]}, awg={"initialised": True}))
    result = invoke(env, ["init", "--yes", *extra])
    assert result.exit_code == 0, result.output
    return yaml.safe_load((env.home / ".maggy" / "harness.yaml").read_text())


def test_init_without_preset_includes_engineering_rules(tmp_path: Path) -> None:
    assert _init(tmp_path, [])["instructions"]["include"] == BASE_RULES


def test_preset_adds_to_engineering_rules(tmp_path: Path) -> None:
    include = _init(tmp_path, ["--preset", "token-economy"])["instructions"]["include"]
    assert include == [*BASE_RULES, "preset:token-economy.md"]


def test_base_rules_exist_in_the_sources(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    assert all((root / rule).is_file() for rule in BASE_RULES)
