"""Managed list entries: user entries beside Maggy's are not conflicts, and
Maggy's own earlier entries are replaced when the profile changes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from harness_emitter_helpers import awg_sources, fixture_profile, make_sources, user_scope

from maggy.harness.apply import apply_changes
from maggy.harness.compile import compile_plan, emitters_for

OPEN = {"write": True, "network": True, "shell": True}
TIGHT = {"write": "workspace", "network": "registries", "shell": "allowlist"}
USER_HOOK = {"matcher": "Bash", "hooks": [{"type": "command", "command": "~/bin/guard"}]}


@pytest.fixture(autouse=True)
def _no_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


def _profile(perm: dict):
    return fixture_profile(permissions={"profiles": {"workspace": perm}})


def _run(tmp_path: Path, profile, agents=("claude",)):
    scope = user_scope(tmp_path)
    emitters = emitters_for(list(agents), awg_sources(tmp_path))
    changes = compile_plan(profile, scope, emitters)
    apply_changes([c for c in changes if c.status == "ok"], scope.context())
    return changes


def _edit_json(path: Path, edit) -> None:
    data = json.loads(path.read_text())
    edit(data)
    path.write_text(json.dumps(data, indent=2) + "\n")


def test_user_allow_rule_is_not_a_conflict_and_is_kept(tmp_path: Path) -> None:
    _run(tmp_path, _profile(TIGHT))
    settings = user_scope(tmp_path).root / ".claude" / "settings.json"
    _edit_json(settings, lambda d: d["permissions"]["allow"].append("Bash(git status)"))
    _edit_json(settings, lambda d: d["hooks"]["PostToolUse"].append(USER_HOOK))
    changes = _run(tmp_path, fixture_profile(hooks={"after_edit": ["fmt"]}))
    [change] = [c for c in changes if c.path == settings]
    assert change.status == "ok", (change.reason, change.conflicts)
    data = json.loads(settings.read_text())
    assert "Bash(git status)" in data["permissions"]["allow"]
    assert USER_HOOK in data["hooks"]["PostToolUse"]
    assert "Stop" not in data["hooks"]


def test_tightening_removes_maggys_broad_rules(tmp_path: Path) -> None:
    _run(tmp_path, _profile(OPEN))
    settings = user_scope(tmp_path).root / ".claude" / "settings.json"
    _edit_json(settings, lambda d: d["permissions"]["allow"].insert(0, "Read(~/notes)"))
    _run(tmp_path, _profile(TIGHT))
    allow = json.loads(settings.read_text())["permissions"]["allow"]
    assert "Bash" not in allow and "WebFetch" not in allow and "WebSearch" not in allow
    assert allow[0] == "Read(~/notes)" and "Bash(pytest -q)" in allow


def test_removing_a_maggy_rule_on_disk_is_a_conflict(tmp_path: Path) -> None:
    _run(tmp_path, _profile(TIGHT))
    settings = user_scope(tmp_path).root / ".claude" / "settings.json"
    _edit_json(settings, lambda d: d["permissions"]["allow"].remove("Bash(pytest -q)"))
    [change] = [c for c in compile_plan(_profile(TIGHT), user_scope(tmp_path),
                                        emitters_for(["claude"], make_sources(tmp_path)))
                if c.path == settings]
    assert change.status == "conflict" and change.conflicts == ["permissions.allow[]"]


def test_opencode_and_pi_user_list_entries_are_not_conflicts(tmp_path: Path) -> None:
    _run(tmp_path, fixture_profile(), ("opencode", "pi"))
    home = user_scope(tmp_path).root
    oc, pi = home / ".config" / "opencode" / "opencode.json", home / ".pi" / "agent" / "settings.json"
    _edit_json(oc, lambda d: d["instructions"].append("~/my-rules.md"))
    _edit_json(oc, lambda d: d["plugin"].append("my-plugin"))
    _edit_json(pi, lambda d: d["skills"].append("~/my-skills"))
    changes = _run(tmp_path, fixture_profile(), ("opencode", "pi"))
    assert all(c.status == "ok" for c in changes if c.path in (oc, pi))
    assert "~/my-rules.md" in json.loads(oc.read_text())["instructions"]
    assert "my-plugin" in json.loads(oc.read_text())["plugin"]
    assert "~/my-skills" in json.loads(pi.read_text())["skills"]
