"""Sub-commands registered on the main `maggy` app (kept out of cli.py)."""

from __future__ import annotations

from collections.abc import Callable

import typer

from maggy.cli_analytics import register as register_analytics
from maggy.harness.cli import app as harness_app
from maggy.worker.cli import app as worker_app


def register(app: typer.Typer, client, ensure: Callable[[], bool]) -> None:
    """Analytics/reporting commands (route, budget, models, ...), `maggy harness`, `maggy worker`."""
    register_analytics(app, client, ensure)
    app.add_typer(harness_app, name="harness")
    app.add_typer(worker_app, name="worker")
