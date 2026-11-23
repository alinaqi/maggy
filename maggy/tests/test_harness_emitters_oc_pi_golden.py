"""Golden plans for the OpenCode and pi emitters (RFC personal-harness §2.2)."""

from __future__ import annotations

from pathlib import Path

import pytest
from harness_emitter_helpers import (
    assert_golden, awg_sources, fixture_profile, project_scope, serialize, user_scope,
)

from maggy.harness.emitters import OpenCodeEmitter, PiEmitter

CASES = [
    (OpenCodeEmitter, user_scope, "opencode_user.txt"),
    (OpenCodeEmitter, project_scope, "opencode_project.txt"),
    (PiEmitter, user_scope, "pi_user.txt"),
    (PiEmitter, project_scope, "pi_project.txt"),
]


@pytest.fixture(autouse=True)
def _no_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


@pytest.mark.parametrize("case", CASES, ids=[c[2] for c in CASES])
def test_plan_matches_golden(tmp_path: Path, case) -> None:
    emitter_cls, make_scope, golden = case
    emitter = emitter_cls(awg_sources(tmp_path))
    changes = emitter.plan(fixture_profile(), make_scope(tmp_path))
    assert_golden(golden, serialize(changes, tmp_path))


@pytest.mark.parametrize("case", CASES, ids=[c[2] for c in CASES])
def test_plan_is_deterministic_and_writes_nothing(tmp_path: Path, case) -> None:
    emitter_cls, make_scope, _ = case
    emitter = emitter_cls(awg_sources(tmp_path))
    scope = make_scope(tmp_path)
    before = sorted(tmp_path.rglob("*"))
    first = serialize(emitter.plan(fixture_profile(), scope), tmp_path)
    second = serialize(emitter.plan(fixture_profile(), scope), tmp_path)
    assert first == second
    assert sorted(tmp_path.rglob("*")) == before


def test_agent_names(tmp_path: Path) -> None:
    sources = awg_sources(tmp_path)
    assert OpenCodeEmitter(sources).agent == "opencode"
    assert PiEmitter(sources).agent == "pi"
