"""Golden plans for the Claude Code and Codex emitters (RFC personal-harness §2.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from harness_emitter_helpers import (
    assert_golden, fixture_profile, make_sources, project_scope, serialize, user_scope,
)

from maggy.harness.emitters import ClaudeEmitter, CodexEmitter

CASES = [
    (ClaudeEmitter, user_scope, "claude_user.txt"),
    (ClaudeEmitter, project_scope, "claude_project.txt"),
    (CodexEmitter, user_scope, "codex_user.txt"),
    (CodexEmitter, project_scope, "codex_project.txt"),
]


@pytest.mark.parametrize("case", CASES, ids=[c[2] for c in CASES])
def test_plan_matches_golden(tmp_path: Path, case) -> None:
    emitter_cls, make_scope, golden = case
    emitter = emitter_cls(make_sources(tmp_path))
    changes = emitter.plan(fixture_profile(), make_scope(tmp_path))
    assert_golden(golden, serialize(changes, tmp_path))


@pytest.mark.parametrize("case", CASES, ids=[c[2] for c in CASES])
def test_plan_is_deterministic_and_writes_nothing(tmp_path: Path, case) -> None:
    emitter_cls, make_scope, _ = case
    emitter = emitter_cls(make_sources(tmp_path))
    scope = make_scope(tmp_path)
    before = sorted(p for p in tmp_path.rglob("*"))
    first = serialize(emitter.plan(fixture_profile(), scope), tmp_path)
    second = serialize(emitter.plan(fixture_profile(), scope), tmp_path)
    assert first == second
    assert sorted(p for p in tmp_path.rglob("*")) == before


def test_agent_names(tmp_path: Path) -> None:
    sources = make_sources(tmp_path)
    assert ClaudeEmitter(sources).agent == "claude"
    assert CodexEmitter(sources).agent == "codex"
