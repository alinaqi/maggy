"""Token-economy preset: the personal tier table lives in a preset, not the repo CLAUDE.md."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from harness_cli_helpers import TESTED, FakeTools, invoke, make_env
from harness_emitter_helpers import make_sources

from maggy.harness.emitters.sources import instructions_body
from maggy.harness.errors import HarnessConfigError
from maggy.harness.schema import HarnessProfile

REPO_CLAUDE = Path(__file__).resolve().parents[2] / "CLAUDE.md"
PRESET_MD = Path(__file__).resolve().parents[1] / "maggy" / "harness" / "presets" / "token-economy.md"
PERSONAL = ["| Tier | Model | Cost", "DeepSeek V4 Pro", "Kimi K2.6", "Grok 4.3", "deepseek --pro",
            "deepseek --flash", "kimi \"", "grok \"", "gemini --pro-search", "agy-delegate",
            "~/bin/review --all", "~/bin/validate-plan", "~/bin/research", "pr-review",
            "FOLLOWED MODEL", "Routing heuristic"]
GENERIC = ["TDD", "Quality Gates", "CHANGELOG.md", "functions per file"]


def test_repo_claude_md_keeps_only_generic_policy() -> None:
    text = REPO_CLAUDE.read_text()
    assert [marker for marker in PERSONAL if marker in text] == []
    assert "~/bin" not in text
    assert [marker for marker in GENERIC if marker.lower() not in text.lower()] == []


def test_preset_reproduces_tier_table_and_tool_invocations() -> None:
    text = PRESET_MD.read_text()
    assert [marker for marker in PERSONAL if marker not in text] == []


def test_preset_include_resolves_from_the_package(tmp_path: Path) -> None:
    profile = HarnessProfile.model_validate({"instructions": {"include": ["preset:token-economy.md"]}})
    body = instructions_body(make_sources(tmp_path), profile)
    assert body == PRESET_MD.read_text().strip()


@pytest.mark.parametrize("bad", ["preset:../schema.py", "preset:missing.md"])
def test_preset_include_rejects_unknown_or_escaping_names(tmp_path: Path, bad: str) -> None:
    profile = HarnessProfile.model_validate({"instructions": {"include": [bad]}})
    with pytest.raises(HarnessConfigError, match="instructions.include"):
        instructions_body(make_sources(tmp_path), profile)


def test_init_preset_token_economy_includes_it(tmp_path: Path) -> None:
    env = make_env(tmp_path, FakeTools({"codex": TESTED["codex"]}))
    result = invoke(env, ["init", "--yes", "--preset", "token-economy"])
    assert result.exit_code == 0, result.output
    profile = yaml.safe_load((env.home / ".maggy" / "harness.yaml").read_text())
    assert "preset:token-economy.md" in profile["instructions"]["include"]
    assert profile["models"]["tiers"]["main"] == "deepseek-pro"
    assert profile["agents"]["installed"] == ["codex"]


def test_init_without_preset_has_no_personal_rules(tmp_path: Path) -> None:
    env = make_env(tmp_path, FakeTools({"codex": TESTED["codex"]}))
    invoke(env, ["init", "--yes"])
    profile = yaml.safe_load((env.home / ".maggy" / "harness.yaml").read_text())
    assert "instructions" not in profile


def test_init_unknown_preset_fails_and_names_choices(tmp_path: Path) -> None:
    env = make_env(tmp_path, FakeTools({"codex": TESTED["codex"]}))
    result = invoke(env, ["init", "--yes", "--preset", "nope"])
    assert result.exit_code != 0
    assert "token-economy" in result.output
    assert not (env.home / ".maggy" / "harness.yaml").exists()
