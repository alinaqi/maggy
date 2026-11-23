"""Fakes for the `maggy harness` CLI tests: no real awg, agents or HOME."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml
from harness_emitter_helpers import make_sources
from typer.testing import CliRunner

from maggy.harness.cli import ToolEnv, app

TESTED = {"claude": "2.1.330", "codex": "0.163.0", "opencode": "1.19.6", "pi": "0.73.1"}


class FakeTools:
    """PATH + subprocess stand-in; records every argv it is asked to run."""

    def __init__(self, versions: dict[str, str], awg: dict | None = None) -> None:
        self.versions = versions
        self.awg = awg
        self.calls: list[list[str]] = []

    def which(self, name: str) -> str | None:
        known = name in self.versions or (name == "awg" and self.awg is not None)
        return f"/fake/bin/{name}" if known else None

    def run(self, argv: list[str]) -> subprocess.CompletedProcess:
        assert isinstance(argv, list), "subprocess calls must be argv lists"
        self.calls.append(argv)
        if argv[1:] == ["--version"]:
            return _done(argv, 0, f"{self.versions[argv[0]]} ({argv[0]})\n")
        return self._awg(argv)

    def _awg(self, argv: list[str]) -> subprocess.CompletedProcess:
        awg = self.awg
        if argv[1:] == ["status"]:
            return _done(argv, 0 if awg["initialised"] else 1, "")
        if argv[1:] == ["init"]:
            awg["initialised"] = True
            return _done(argv, 0, "AWG Local ready\n")
        if argv[1:3] == ["token", "mint"]:
            if awg.get("mint_fails"):
                return _done(argv, 1, "")
            return _done(argv, 0, json.dumps({"token": f"SECRET-{argv[3]}", "kind": "agent"}))
        if argv[1] == "--token-file":
            ok = Path(argv[2]).name not in awg.get("unreachable", ())
            return _done(argv, 0 if ok else 1, "")
        return _done(argv, 2, "unexpected")


def _done(argv: list[str], code: int, out: str) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(argv, code, out, "")


def make_env(tmp_path: Path, tools: FakeTools) -> ToolEnv:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return ToolEnv(run=tools.run, which=tools.which, home=home, sources=make_sources(tmp_path))


def invoke(env: ToolEnv, args: list[str], text: str | None = None):
    return CliRunner().invoke(app, args, obj=env, input=text, catch_exceptions=False)


def write_profile(env: ToolEnv, data: dict) -> Path:
    path = env.home / ".maggy" / "harness.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data))
    return path


def write_tokens(env: ToolEnv, agents: list[str]) -> None:
    tokens = env.home / ".maggy" / "tokens"
    tokens.mkdir(parents=True, exist_ok=True)
    for agent in [*agents, "runner-agent", "runner-ci"]:
        (tokens / f"{agent}.token").write_text("x")
        (tokens / f"{agent}.token").chmod(0o600)
