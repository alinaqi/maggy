"""pi emitter placement, checked against pi 0.73.1's own docs
(node_modules/@mariozechner/pi-coding-agent/docs):

- settings.md "Settings": ~/.pi/agent/settings.json (global), .pi/settings.json
  (project); "Resources": `skills` is a list of files or directories, paths in
  ~/.pi/agent/settings.json resolve relative to ~/.pi/agent, absolute allowed.
- README.md "Context Files": ~/.pi/agent/AGENTS.md (global) and AGENTS.md in the repo.
- skills.md "Locations": ~/.pi/agent/skills/ (global), .pi/skills/ (project);
  directories containing SKILL.md are discovered.
- extensions.md "Extension Locations": ~/.pi/agent/extensions/*.ts and
  ~/.pi/agent/extensions/*/index.ts (global), .pi/extensions/... (project);
  "Events": session_start, tool_call (can block), tool_result, agent_end,
  session_before_compact, session_shutdown.
"""

from __future__ import annotations

import json
from pathlib import Path

from harness_emitter_helpers import (
    awg_sources, by_name, fixture_profile, make_sources, project_scope, user_scope,
)

from maggy.harness.emitters import PiEmitter

EXT_MARKER = "// maggy:managed-extension"


def _plan(tmp_path: Path, scope, profile=None):
    return PiEmitter(awg_sources(tmp_path)).plan(profile or fixture_profile(), scope)


def test_user_scope_placement(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    agent = scope.home / ".pi" / "agent"
    paths = {c.path for c in _plan(tmp_path, scope)}
    assert {agent / "AGENTS.md", agent / "settings.json", agent / "awg.json",
            agent / "skills" / "python" / "SKILL.md", agent / "extensions" / "awg" / "index.ts",
            agent / "extensions" / "awg" / "run.ts", agent / "extensions" / "maggy-hooks.ts"} <= paths


def test_project_scope_placement_has_no_awg(tmp_path: Path) -> None:
    scope = project_scope(tmp_path)
    changes = _plan(tmp_path, scope)
    paths = {c.path for c in changes}
    assert {scope.root / "AGENTS.md", scope.root / ".pi" / "skills" / "python" / "SKILL.md",
            scope.root / ".pi" / "extensions" / "maggy-hooks.ts"} <= paths
    assert not any("awg" in str(p.relative_to(tmp_path)) for p in paths)


def test_awg_extension_copied_with_marker(tmp_path: Path) -> None:
    change = by_name(_plan(tmp_path, user_scope(tmp_path)), "extensions/awg/run.ts")
    source = (tmp_path / "awg-repo" / "plugins" / "pi" / "extensions" / "awg" / "run.ts").read_text()
    assert change.kind == "create" and change.after == f"{EXT_MARKER}\n{source}"


def test_awg_token_file_and_skill_in_settings(tmp_path: Path) -> None:
    scope = user_scope(tmp_path)
    changes = _plan(tmp_path, scope)
    awg = by_name(changes, "awg.json")
    token = str(scope.home / ".maggy" / "tokens" / "pi.token")
    assert json.loads(awg.after) == {"tokenFile": token} and awg.references_token
    settings = json.loads(by_name(changes, "settings.json").after)
    assert settings == {"skills": [str(tmp_path / "awg-repo" / "plugins" / "pi" / "skills")]}


def test_hooks_extension_maps_abstract_events(tmp_path: Path) -> None:
    text = by_name(_plan(tmp_path, user_scope(tmp_path)), "maggy-hooks.ts").after
    assert text.startswith(EXT_MARKER + "\n")
    for event in ("session_start", "tool_call", "tool_result", "agent_end",
                  "session_before_compact", "session_shutdown"):
        assert f'"{event}"' in text
    assert '"load-memory"' in text and '"lint-changed"' in text and '"run-focused-tests"' in text


def test_no_hooks_extension_without_hooks(tmp_path: Path) -> None:
    changes = _plan(tmp_path, user_scope(tmp_path), fixture_profile(hooks={}))
    assert not any(c.path.name == "maggy-hooks.ts" for c in changes)


def test_no_awg_files_without_awg_repo(tmp_path: Path) -> None:
    changes = PiEmitter(make_sources(tmp_path)).plan(fixture_profile(), user_scope(tmp_path))
    assert not any("awg" in str(c.path.relative_to(tmp_path)) for c in changes)


def test_capabilities_are_honest(tmp_path: Path) -> None:
    caps = PiEmitter(make_sources(tmp_path)).capabilities()
    assert caps.instructions.level == "native" and caps.skills.level == "native"
    assert caps.hooks.level == "partial" and "payload" in caps.hooks.notes
    assert caps.mcp.level == "partial" and "extension" in caps.mcp.notes
    assert caps.permissions.level == "none" and "--tools" in caps.permissions.notes
