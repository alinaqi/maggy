"""CLI entry point for Polyphony.

Usage:
    polyphony init          Create ~/.polyphony/ with config files
    polyphony spawn <title> Create and route a task
    polyphony status        Show current task states
    polyphony cleanup       Remove completed workspaces
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import (
    default_config_dir,
    load_agents,
    load_config,
    load_identities,
    load_routing,
)
from .store import PolyphonyStore


def cmd_init(args: argparse.Namespace) -> int:
    """Create config directory with templates."""
    cfg_dir = default_config_dir()
    cfg_dir.mkdir(parents=True, exist_ok=True)
    print(f"Initialized {cfg_dir}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Show task states from the store."""
    cfg = load_config()
    store_dir = Path(cfg.get("workspace_root", "~/.polyphony"))
    store_dir = store_dir.expanduser()
    store = PolyphonyStore(store_dir)
    store.init_db()
    tasks = store.list_tasks()
    if not tasks:
        print("No tasks.")
        return 0
    for t in tasks:
        print(f"  [{t.state:12s}] {t.id[:8]}  {t.title}")
    return 0


def cmd_spawn(args: argparse.Namespace) -> int:
    """Create a task from CLI."""
    from .models import Task
    from .store import PolyphonyStore

    cfg = load_config()
    store_dir = Path(cfg.get("workspace_root", "~/.polyphony"))
    store_dir = store_dir.expanduser()
    store = PolyphonyStore(store_dir)
    store.init_db()
    task = Task(
        title=args.title,
        source="local",
        source_ref="cli",
        task_type=args.type,
    )
    store.save_task(task)
    print(f"Created task {task.id[:8]}: {task.title}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="polyphony",
        description="Multi-agent orchestration",
    )
    parser.add_argument(
        "--version", action="version",
        version=f"polyphony {__version__}",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Initialize config")
    sub.add_parser("status", help="Show task states")

    spawn_p = sub.add_parser("spawn", help="Create a task")
    spawn_p.add_argument("title", help="Task title")
    spawn_p.add_argument(
        "--type", default="feature",
        help="Task type",
    )

    sub.add_parser("cleanup", help="Remove workspaces")
    return parser


def main() -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    dispatch = {
        "init": cmd_init,
        "status": cmd_status,
        "spawn": cmd_spawn,
    }

    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
