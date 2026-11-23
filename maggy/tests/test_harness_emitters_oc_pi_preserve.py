"""OpenCode and pi emitters keep user content; Maggy copies are removable; no token literals."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from harness_emitter_helpers import (
    awg_sources, by_name, fixture_profile, project_scope, user_scope, write,
)

from maggy.harness.apply import apply_changes
from maggy.harness.emitters import OpenCodeEmitter, PiEmitter

USER_OC = {"model": "anthropic/x", "instructions": ["docs/style.md"],
           "mcp": {"other": {"type": "local", "command": ["x"]}},
           "permission": {"bash": {"git *": "allow"}, "read": "allow"},
           "plugin": ["opencode-foo"], "skills": {"paths": ["/opt/skills"]}}


@pytest.fixture(autouse=True)
def _no_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


def _apply(emitter, profile, scope):
    changes = emitter.plan(profile, scope)
    report = apply_changes(changes, scope.context())
    assert not report.skipped, report.skipped
    return changes


def test_opencode_user_content_preserved(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    cfg = write(scope.home / ".config" / "opencode" / "opencode.json", json.dumps(USER_OC, indent=2))
    agents = write(scope.home / ".config" / "opencode" / "AGENTS.md", "# Mine\n\nkeep\n")
    _apply(OpenCodeEmitter(awg_sources(tmp_path)), fixture_profile(), scope)
    data = json.loads(cfg.read_text())
    assert data["model"] == "anthropic/x" and data["mcp"]["other"] == USER_OC["mcp"]["other"]
    assert data["instructions"][0] == "docs/style.md" and len(data["instructions"]) == 2
    assert data["permission"]["read"] == "allow"
    assert data["permission"]["bash"]["git *"] == "allow"
    assert list(data["permission"]["bash"])[0] == "*"
    assert data["plugin"][0] == "opencode-foo" and len(data["plugin"]) == 2
    assert data["skills"]["paths"][0] == "/opt/skills"
    assert agents.read_text().startswith("# Mine\n\nkeep\n")


def test_pi_user_content_preserved(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    agent = scope.home / ".pi" / "agent"
    settings = write(agent / "settings.json", json.dumps({"theme": "light", "skills": ["~/.claude/skills"]}))
    awg = write(agent / "awg.json", json.dumps({"bin": "/usr/local/bin/awg"}))
    mine = write(agent / "extensions" / "mine.ts", "export default () => {}\n")
    _apply(PiEmitter(awg_sources(tmp_path)), fixture_profile(), scope)
    data = json.loads(settings.read_text())
    assert data["theme"] == "light" and data["skills"][0] == "~/.claude/skills"
    assert len(data["skills"]) == 2
    assert json.loads(awg.read_text())["bin"] == "/usr/local/bin/awg"
    assert mine.read_text() == "export default () => {}\n"


def test_pi_removed_hooks_and_awg_delete_only_managed(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    ext = scope.home / ".pi" / "agent" / "extensions"
    emitter = PiEmitter(awg_sources(tmp_path))
    _apply(emitter, fixture_profile(), scope)
    own = write(ext / "awg" / "notes.ts", "// mine\n")
    changes = _apply(emitter, fixture_profile(hooks={}, work={"provider": "none"}), scope)
    assert by_name(changes, "maggy-hooks.ts").kind == "delete"
    assert not (ext / "maggy-hooks.ts").exists() and not (ext / "awg" / "index.ts").exists()
    assert own.read_text() == "// mine\n"


def test_pi_user_extension_with_same_path_is_not_overwritten(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    own = write(scope.home / ".pi" / "agent" / "extensions" / "awg" / "index.ts", "// my own awg\n")
    changes = PiEmitter(awg_sources(tmp_path)).plan(fixture_profile(), scope)
    change = by_name(changes, "awg/index.ts")
    assert change.status == "conflict" and "not managed by Maggy" in change.reason
    apply_changes(changes, scope.context())
    assert own.read_text() == "// my own awg\n"


def test_pi_edited_managed_extension_is_a_conflict(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    emitter = PiEmitter(awg_sources(tmp_path))
    _apply(emitter, fixture_profile(), scope)
    run = scope.home / ".pi" / "agent" / "extensions" / "awg" / "run.ts"
    run.write_text(run.read_text() + "// tweak\n")
    assert by_name(emitter.plan(fixture_profile(), scope), "awg/run.ts").status == "conflict"


@pytest.mark.parametrize("make_scope", [user_scope, project_scope])
def test_reapply_is_unchanged(tmp_path: Path, make_scope) -> None:
    scope = make_scope(tmp_path)
    for emitter in (OpenCodeEmitter(awg_sources(tmp_path)), PiEmitter(awg_sources(tmp_path))):
        _apply(emitter, fixture_profile(), scope)
        again = emitter.plan(fixture_profile(), scope)
        assert {(c.kind, c.status) for c in again} == {("unchanged", "ok")}
