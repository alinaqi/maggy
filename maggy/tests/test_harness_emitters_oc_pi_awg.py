"""OpenCode and pi AWG wiring: token files referenced, never inlined; honest capabilities."""

from __future__ import annotations

from pathlib import Path

import pytest
from harness_emitter_helpers import awg_sources, fixture_profile, make_sources, project_scope, user_scope
from test_harness_emitters_awg import TOKEN_LITERALS

from maggy.harness.emitters import OpenCodeEmitter, PiEmitter


@pytest.fixture(autouse=True)
def _no_xdg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


def _all_plans(tmp_path: Path):
    for emitter_cls in (OpenCodeEmitter, PiEmitter):
        for make_scope in (user_scope, project_scope):
            yield from emitter_cls(awg_sources(tmp_path)).plan(fixture_profile(), make_scope(tmp_path))


def test_no_token_literals_and_no_minting(tmp_path: Path) -> None:
    for change in _all_plans(tmp_path):
        assert not any(p.search(change.after or "") for p in TOKEN_LITERALS), change.path
    assert not (tmp_path / "home" / ".maggy" / "tokens").exists()


def test_token_referencing_files_are_flagged(tmp_path: Path) -> None:
    flagged = {c.path.name for e in (OpenCodeEmitter, PiEmitter)
               for c in e(awg_sources(tmp_path)).plan(fixture_profile(), user_scope(tmp_path))
               if c.references_token}
    assert {"opencode.json", "awg.json"} <= flagged


@pytest.mark.parametrize("emitter_cls", [OpenCodeEmitter, PiEmitter])
def test_no_awg_wiring_when_work_provider_none(tmp_path: Path, emitter_cls) -> None:
    profile = fixture_profile(work={"provider": "none"})
    changes = emitter_cls(awg_sources(tmp_path)).plan(profile, user_scope(tmp_path))
    text = "".join((c.after or "").replace(str(tmp_path), "") + str(c.path.relative_to(tmp_path))
                   for c in changes)
    assert "awg" not in text.lower()


def test_opencode_capabilities_are_honest(tmp_path: Path) -> None:
    caps = OpenCodeEmitter(make_sources(tmp_path)).capabilities()
    assert caps.instructions.level == "native" and caps.mcp.level == "native"
    assert caps.skills.level == "native" and caps.permissions.level == "partial"
    assert caps.hooks.level == "none" and "runner" in caps.hooks.notes
