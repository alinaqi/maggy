"""`maggy harness`: init, show, doctor, diff, apply."""

from __future__ import annotations

import typer

from maggy.harness.cli.doctor_cmd import doctor
from maggy.harness.cli.env import ToolEnv
from maggy.harness.cli.init_cmd import init
from maggy.harness.cli.plan_cmd import apply, diff
from maggy.harness.cli.show_cmd import show

app = typer.Typer(help="Personal harness: one profile compiled into every agent's config.",
                  no_args_is_help=True)
for _command in (init, show, doctor, diff, apply):
    app.command()(_command)

__all__ = ["ToolEnv", "app"]
