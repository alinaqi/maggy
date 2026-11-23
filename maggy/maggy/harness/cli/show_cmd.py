"""`maggy harness show`: the resolved profile, one key per line, with its source."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from maggy.harness.cli.env import get_env
from maggy.harness.cli.options import REPO, config_errors, load
from maggy.harness.layering import join


def leaves(data: dict, prefix: str = "") -> list[tuple[str, object]]:
    """(key path, value) for every leaf; lists and empty dicts are leaves."""
    out: list[tuple[str, object]] = []
    for key, value in data.items():
        path = join(prefix, key)
        nested = isinstance(value, dict) and value
        out += leaves(value, path) if nested else [(path, value)]
    return out


def source_of(path: str, provenance: dict[str, str]) -> str:
    """The nearest recorded source for a key path or its ancestors."""
    parts = path.split(".")
    for size in range(len(parts), 0, -1):
        found = provenance.get(".".join(parts[:size]))
        if found:
            return found
    return "default"


def show(ctx: typer.Context, repo: Path = REPO) -> None:
    """Print the resolved profile with the source of every key."""
    env = get_env(ctx)
    with config_errors():
        resolved = load(env, repo or Path.cwd())
    rows = leaves(resolved.profile.model_dump(mode="json"))
    width = max(len(path) for path, _ in rows)
    for path, value in rows:
        shown = value if isinstance(value, str) else json.dumps(value)
        typer.echo(f"{path:<{width}}  {shown}  {source_of(path, resolved.provenance)}")
