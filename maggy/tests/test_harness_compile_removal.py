"""compile_plan: wiring dropped from the profile is removed, per agent and scope."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from harness_emitter_helpers import awg_sources, fixture_profile, make_sources, project_scope, user_scope

from maggy.harness.apply import apply_changes
from maggy.harness.compile import AGENTS, compile_plan, emitters_for


@pytest.fixture(autouse=True)
def _no_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


def _apply(profile, scope, emitters) -> None:
    report = apply_changes(compile_plan(profile, scope, emitters), scope.context())
    assert not report.skipped, report.skipped


def test_work_provider_none_removes_awg_wiring(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    emitters = emitters_for(["codex", "claude"], make_sources(tmp_path))
    _apply(fixture_profile(), scope, emitters)
    _apply(fixture_profile(work={"provider": "none"}), scope, emitters)
    home = scope.root
    assert "awg" not in (home / ".codex" / "config.toml").read_text()
    assert "maggy:begin awg" not in (home / ".codex" / "AGENTS.md").read_text()
    assert "awg" not in json.loads((home / ".claude.json").read_text()).get("mcpServers", {})
    again = compile_plan(fixture_profile(work={"provider": "none"}), scope, emitters)
    assert all(c.kind == "unchanged" and c.status == "ok" for c in again)


def test_file_no_longer_emitted_loses_its_regions(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    emitters = emitters_for(["codex"], make_sources(tmp_path))
    _apply(fixture_profile(instructions={"include": []}), scope, emitters)
    agents = scope.root / ".codex" / "AGENTS.md"
    assert "maggy:begin awg" in agents.read_text()
    _apply(fixture_profile(instructions={"include": []}, work={"provider": "none"}), scope, emitters)
    assert "maggy:begin" not in agents.read_text()


def test_partial_run_keeps_other_agents_regions_tracked(tmp_path: Path) -> None:
    scope = project_scope(tmp_path)
    sources = awg_sources(tmp_path)
    full = emitters_for(list(AGENTS), sources)
    _apply(fixture_profile(), scope, full)
    _apply(fixture_profile(), scope, emitters_for(["claude"], sources))
    agents = scope.root / "AGENTS.md"
    assert "maggy:begin awg" in agents.read_text()
    agents.write_text(agents.read_text().replace("AWG", "XXX", 1))
    [change] = [c for c in compile_plan(fixture_profile(), scope, full) if c.path == agents]
    assert change.status == "conflict" and "awg" in change.conflicts


def test_user_scope_run_ignores_project_regions_under_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    repo = home / "code" / "repo"
    repo.mkdir(parents=True)
    project = project_scope(tmp_path).model_copy(update={"root": repo})
    emitters = emitters_for(["codex"], make_sources(tmp_path))
    _apply(fixture_profile(), project, emitters)
    _apply(fixture_profile(work={"provider": "none"}), user_scope(tmp_path), emitters)
    assert "maggy:begin awg" in (repo / "AGENTS.md").read_text()
