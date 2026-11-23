"""First apply never silently replaces a value the user already has at a managed key.

RFC personal-harness §2.2: JSON and TOML managed keys merge without touching
user keys. A key with no harness.lock entry whose on-disk value differs from the
profile is a conflict (--take-profile overwrites, --take-mine keeps it).
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from harness_emitter_helpers import by_name, fixture_profile, make_sources, user_scope, write

from maggy.harness.apply import apply_changes
from maggy.harness.emitters import CodexEmitter, OpenCodeEmitter
from maggy.harness.schema import HarnessProfile

STRICT_CODEX = 'sandbox_mode = "read-only"\napproval_policy = "untrusted"\n'
DENY_OPENCODE = {"permission": {"bash": "deny", "edit": "deny"}}
OPEN_PERMS = {"profiles": {"open": {"write": "workspace", "network": True, "shell": True}}}


def _open_profile() -> HarnessProfile:
    return fixture_profile(permissions=OPEN_PERMS, worker={"permission": "open"})


def _codex_change(tmp_path: Path, profile: HarnessProfile, resolution=None):
    scope = user_scope(tmp_path).model_copy(update={"resolution": resolution})
    config = write(scope.home / ".codex" / "config.toml", STRICT_CODEX)
    changes = CodexEmitter(make_sources(tmp_path)).plan(profile, scope)
    return by_name(changes, "config.toml"), config, scope


def test_default_profile_does_not_touch_codex_sandbox(tmp_path: Path) -> None:
    change, _, _ = _codex_change(tmp_path, HarnessProfile())
    assert change.status == "ok"
    assert (change.after or STRICT_CODEX).startswith(STRICT_CODEX)


def test_differing_codex_sandbox_is_a_conflict_on_first_apply(tmp_path: Path) -> None:
    change, _, _ = _codex_change(tmp_path, _open_profile())
    assert change.status == "conflict"
    assert set(change.conflicts) >= {"sandbox_mode", "approval_policy"}
    assert change.after == STRICT_CODEX


def test_take_profile_overwrites_and_take_mine_keeps(tmp_path: Path) -> None:
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
    change, config, scope = _codex_change(tmp_path / "a", _open_profile(), "take_profile")
    apply_changes([change], scope.context())
    assert tomllib.loads(config.read_text())["sandbox_mode"] == "workspace-write"
    change, config, scope = _codex_change(tmp_path / "b", _open_profile(), "take_mine")
    apply_changes([change], scope.context())
    assert tomllib.loads(config.read_text())["sandbox_mode"] == "read-only"


def test_kept_value_stays_pinned_on_the_next_apply(tmp_path: Path) -> None:
    change, config, scope = _codex_change(tmp_path, _open_profile(), "take_mine")
    apply_changes([change], scope.context())
    again = by_name(CodexEmitter(make_sources(tmp_path)).plan(_open_profile(), user_scope(tmp_path)),
                    "config.toml")
    assert again.status == "ok"
    assert tomllib.loads(again.after)["approval_policy"] == "untrusted"


def test_opencode_existing_deny_is_a_conflict_not_loosened(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    path = write(scope.home / ".config" / "opencode" / "opencode.json", json.dumps(DENY_OPENCODE))
    change = by_name(OpenCodeEmitter(make_sources(tmp_path)).plan(_open_profile(), scope), "opencode.json")
    assert change.status == "conflict"
    assert {"permission.bash", "permission.edit"} <= set(change.conflicts)
    assert json.loads(path.read_text()) == DENY_OPENCODE


def test_equal_existing_value_is_adopted_without_conflict(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    same = {"permission": {"bash": "allow", "edit": "allow", "webfetch": "allow", "websearch": "allow"}}
    write(scope.home / ".config" / "opencode" / "opencode.json", json.dumps(same))
    change = by_name(OpenCodeEmitter(make_sources(tmp_path)).plan(_open_profile(), scope), "opencode.json")
    assert change.status == "ok"
    assert set(change.lock_entries) >= {"permission.bash", "permission.edit"}
