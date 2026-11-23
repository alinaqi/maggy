"""Sub-command registration kept out of the oversized maggy/cli.py."""

from __future__ import annotations

import typer
from typer.testing import CliRunner


def test_register_adds_harness_worker_run_and_analytics_commands() -> None:
    from maggy.cli_extensions import register

    app = typer.Typer()
    register(app, client=None, ensure=lambda: True)
    assert [group.name for group in app.registered_groups] == ["harness", "worker", "run"]
    assert app.registered_commands, "analytics commands should be registered"
    assert CliRunner().invoke(app, ["harness", "--help"]).exit_code == 0
