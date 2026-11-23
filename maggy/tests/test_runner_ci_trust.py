"""CI trust is not enforceable under host execution: doctor and `maggy run` say so."""

from __future__ import annotations

from pathlib import Path

import typer
from typer.testing import CliRunner

from maggy.harness.cli.doctor_checks import host_execution_warnings
from maggy.runner import cli as run_cli
from maggy.runner.session import RunReport
from worker_git_helpers import profile

DOCS = Path(__file__).resolve().parents[2] / "docs" / "runner.md"


def test_doctor_warns_ci_trust_is_not_enforced_on_the_host() -> None:
    warnings = " ".join(host_execution_warnings(profile()))
    assert "runner-ci.token" in warnings and "CI trust" in warnings


def test_run_warns_ci_trust_is_not_enforced_on_the_host(monkeypatch) -> None:
    class Stub:
        config = type("C", (), {"profile": profile()})()

        def run(self, once: bool = False) -> list[RunReport]:
            return [RunReport("idle")]

    monkeypatch.setattr(run_cli, "build_runner", lambda opts: Stub())
    root = typer.Typer()
    root.add_typer(run_cli.app, name="run")
    result = CliRunner().invoke(root, ["run", "--once"])
    assert result.exit_code == 0 and "CI trust" in result.output


def test_docs_state_the_host_execution_limit() -> None:
    text = DOCS.read_text()
    assert "not enforceable" in text and "allow_host_execution" in text
