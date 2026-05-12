"""Analytics and reporting CLI commands."""

from __future__ import annotations

import typer

from maggy.cli_output import (
    console,
    dump_json,
    render_budget,
    render_competitors,
    render_models,
    render_route,
)


def register(app: typer.Typer, client, ensure) -> None:
    """Register analytics commands on the Typer app."""

    @app.command()
    def route(
        blast: int = typer.Argument(..., help="Complexity 1-10"),
        task_type: str = typer.Option("general", "--type"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Get routing decision for a complexity score."""
        ensure()
        data = client.route(blast, task_type)
        dump_json(data) if json_out else render_route(data)

    @app.command()
    def budget(
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Show per-provider token budget."""
        ensure()
        data = client.budget_summary()
        dump_json(data) if json_out else render_budget(data)

    @app.command()
    def models(
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Show model performance heatmap."""
        ensure()
        data = client.models_heatmap()
        dump_json(data) if json_out else render_models(data)

    @app.command()
    def competitors(
        briefing: bool = typer.Option(False, "--briefing"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Show competitor intelligence."""
        ensure()
        if briefing:
            data = client.competitors_briefing()
        else:
            data = client.competitors_news()
        if json_out:
            dump_json(data)
        elif briefing:
            console.print(
                data.get("summary", "No briefing available."),
            )
        else:
            render_competitors(data)

    @app.command()
    def process(
        project: str = typer.Argument(..., help="Project key"),
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Show process health for a project."""
        ensure()
        data = client.process_health(project)
        if json_out:
            dump_json(data)
        else:
            console.print_json(data=data)

    @app.command()
    def config(
        json_out: bool = typer.Option(False, "--json"),
    ) -> None:
        """Show current configuration (redacted)."""
        ensure()
        dump_json(client.config())
