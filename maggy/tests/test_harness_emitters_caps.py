"""Emitter capabilities are honest; inputs that would be unsafe are refused."""

from __future__ import annotations

from pathlib import Path

import pytest
from harness_emitter_helpers import fixture_profile, make_sources, user_scope

from maggy.harness.emitters import ClaudeEmitter, CodexEmitter, Emitter, default_sources
from maggy.harness.errors import HarnessConfigError

AREAS = ("instructions", "skills", "hooks", "mcp", "permissions")


def test_codex_reports_no_native_hooks(tmp_path: Path) -> None:
    caps = CodexEmitter(make_sources(tmp_path)).capabilities()
    assert caps.hooks.level == "none"
    assert "runner" in caps.hooks.notes
    assert caps.instructions.level == "native" and caps.mcp.level == "native"
    assert caps.permissions.level == "partial"


def test_claude_capabilities(tmp_path: Path) -> None:
    caps = ClaudeEmitter(make_sources(tmp_path)).capabilities()
    assert {a: getattr(caps, a).level for a in AREAS} == {
        "instructions": "native", "skills": "native", "hooks": "native",
        "mcp": "native", "permissions": "partial",
    }


@pytest.mark.parametrize("emitter_cls", [ClaudeEmitter, CodexEmitter])
def test_every_capability_has_notes(tmp_path: Path, emitter_cls) -> None:
    emitter = emitter_cls(make_sources(tmp_path))
    assert isinstance(emitter, Emitter)
    caps = emitter.capabilities()
    assert all(getattr(caps, area).notes for area in AREAS)


def test_unsafe_hook_name_is_rejected(tmp_path: Path) -> None:
    profile = fixture_profile(hooks={"before_stop": ["x; rm -rf ~"]})
    with pytest.raises(HarnessConfigError, match="hooks.before_stop"):
        ClaudeEmitter(make_sources(tmp_path)).plan(profile, user_scope(tmp_path))


def test_missing_include_names_the_key(tmp_path: Path) -> None:
    profile = fixture_profile(instructions={"include": ["rules/nope.md"]})
    with pytest.raises(HarnessConfigError, match="instructions.include"):
        CodexEmitter(make_sources(tmp_path)).plan(profile, user_scope(tmp_path))


def test_include_cannot_escape_source_root(tmp_path: Path) -> None:
    (tmp_path / "secret.md").write_text("x")
    profile = fixture_profile(instructions={"include": ["../secret.md"]})
    with pytest.raises(HarnessConfigError, match="outside"):
        CodexEmitter(make_sources(tmp_path)).plan(profile, user_scope(tmp_path))


def test_missing_skill_source_names_the_key(tmp_path: Path) -> None:
    profile = fixture_profile(skills=["does-not-exist"])
    with pytest.raises(HarnessConfigError, match="skills"):
        ClaudeEmitter(make_sources(tmp_path)).plan(profile, user_scope(tmp_path))


def test_default_sources_point_at_maggy_rules_and_skills() -> None:
    root = default_sources().root
    assert (root / "rules").is_dir() and (root / "skills").is_dir()
