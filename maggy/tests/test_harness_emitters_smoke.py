"""Smoke tests with the real CLIs in a throwaway HOME (no credentials, no model call).

Binaries: MAGGY_OPENCODE_BIN / MAGGY_PI_BIN, else `opencode` / `pi` on PATH;
skipped with the reason when absent. pi runs `--mode rpc --offline` with only
`get_commands`, so no prompt is sent (the same check AWG's plugins/pi uses).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from harness_emitter_helpers import awg_sources, fixture_profile, user_scope, write

from maggy.harness.apply import apply_changes
from maggy.harness.emitters import OpenCodeEmitter, PiEmitter

MODEL_EVENTS = {"agent_start", "turn_start", "message_start", "message_update"}


def _binary(name: str) -> str:
    found = os.environ.get(f"MAGGY_{name.upper()}_BIN") or shutil.which(name)
    if not found:
        pytest.skip(f"{name} binary not found (set MAGGY_{name.upper()}_BIN to run this smoke test)")
    return found


def _env(home: Path) -> dict:
    node_dir = str(Path(shutil.which("node") or "/usr/bin/node").parent)
    return {"PATH": os.pathsep.join([node_dir, "/usr/bin", "/bin"]), "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"), "PI_OFFLINE": "1"}


def _emit(emitter, tmp_path: Path):
    scope = user_scope(tmp_path)
    report = apply_changes(emitter.plan(fixture_profile(), scope), scope.context())
    assert not report.skipped, report.skipped
    return scope


def test_opencode_resolves_emitted_config_and_skills(tmp_path: Path, monkeypatch) -> None:
    binary = _binary("opencode")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    scope = _emit(OpenCodeEmitter(awg_sources(tmp_path)), tmp_path)
    run = {"cwd": scope.home, "env": _env(scope.home), "capture_output": True, "text": True, "timeout": 120}
    config = json.loads(subprocess.run([binary, "debug", "config"], check=True, **run).stdout)
    token = str(scope.home / ".maggy" / "tokens" / "opencode.token")
    assert config["mcp"]["awg"]["command"] == ["awg", "mcp", "--token-file", token]
    assert config["permission"]["bash"]["pytest -q"] == "allow"
    skills = json.loads(subprocess.run([binary, "debug", "skill"], check=True, **run).stdout)
    assert {"python", "react-web", "awg"} <= {s["name"] for s in skills}


def _rpc(binary: str, home: Path) -> tuple[list[dict], str]:
    proc = subprocess.run([binary, "--mode", "rpc", "--offline", "--no-session"], cwd=home, env=_env(home),
                          input=json.dumps({"id": "c1", "type": "get_commands"}) + "\n",
                          capture_output=True, text=True, timeout=60, check=False)
    return [json.loads(x) for x in proc.stdout.splitlines() if x.startswith("{")], proc.stderr


def test_pi_loads_emitted_extensions_without_a_model_call(tmp_path: Path) -> None:
    binary = _binary("pi")
    scope = _emit(PiEmitter(awg_sources(tmp_path)), tmp_path)
    ran = scope.home / "session-start-ran"
    hook = write(scope.home / ".maggy" / "hooks" / "load-memory", f"#!/bin/sh\ntouch '{ran}'\n")
    hook.chmod(0o755)
    lines, stderr = _rpc(binary, scope.home)
    answer = next(m for m in lines if m.get("command") == "get_commands")
    assert "awg" in {c["name"] for c in answer["data"]["commands"]}, stderr
    assert not [m for m in lines if m.get("type") == "extension_error"], lines
    assert "Failed to load" not in stderr
    assert not [m for m in lines if m.get("type") in MODEL_EVENTS]
    assert ran.exists(), "maggy-hooks.ts did not run the session_start hook"
