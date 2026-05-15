"""Mnemos CLI — argparse dispatch."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from maggy.mnemos.constants import MNEMOS_DIR


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mnemos",
        description="Task-scoped memory lifecycle",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init", help="Initialize .mnemos/")
    sub.add_parser("status", help="Show status")
    sub.add_parser("fatigue", help="Show fatigue")

    p_cp = sub.add_parser("checkpoint", help="Write checkpoint")
    p_cp.add_argument("--force", action="store_true")

    sub.add_parser("resume", help="Load last checkpoint")
    sub.add_parser("handoff", help="Generate handoff node")

    p_hook = sub.add_parser("_hook", help="Hook dispatch")
    p_hook.add_argument("event")
    p_hook.add_argument("--emergency", action="store_true")

    from maggy.mnemos.cli_nodes import register_node_commands
    register_node_commands(sub)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    from maggy.mnemos.cli_hooks import cmd_hook
    from maggy.mnemos.cli_nodes import cmd_add, cmd_list_nodes

    handlers = {
        "init": _cmd_init,
        "status": _cmd_status,
        "fatigue": _cmd_fatigue,
        "checkpoint": _cmd_checkpoint,
        "resume": _cmd_resume,
        "handoff": _cmd_handoff,
        "_hook": cmd_hook,
        "add": cmd_add,
        "nodes": cmd_list_nodes,
    }
    handlers[args.command](args)


def _require_mnemos_dir() -> Path:
    cwd = Path.cwd()
    d = cwd / MNEMOS_DIR
    if not d.is_dir():
        print(
            "Error: .mnemos/ not found. Run: mnemos init",
            file=sys.stderr,
        )
        sys.exit(1)
    return d


def _cmd_init(_args: argparse.Namespace) -> None:
    from maggy.mnemos.db import MnemosDB

    cwd = Path.cwd()
    mnemos_dir = cwd / MNEMOS_DIR
    if mnemos_dir.is_dir():
        print("Already initialized .mnemos/")
        return
    mnemos_dir.mkdir()
    MnemosDB(mnemos_dir)
    _update_gitignore(cwd)
    print(f"Initialized {mnemos_dir}")


def _update_gitignore(cwd: Path) -> None:
    gi = cwd / ".gitignore"
    entry = ".mnemos/"
    if gi.exists():
        text = gi.read_text()
        if entry in text:
            return
        gi.write_text(text.rstrip() + f"\n{entry}\n")
    else:
        gi.write_text(f"{entry}\n")


def _cmd_status(_args: argparse.Namespace) -> None:
    from maggy.mnemos.db import MnemosDB
    from maggy.mnemos.status import render_status

    d = _require_mnemos_dir()
    db = MnemosDB(d)
    print(render_status(d, db))


def _cmd_fatigue(_args: argparse.Namespace) -> None:
    from maggy.mnemos.fatigue import load_fatigue

    d = _require_mnemos_dir()
    fs = load_fatigue(d)
    if fs is None:
        print("Fatigue: not measured yet")
        return
    print(f"Score: {fs.score:.2f}")
    print(f"State: {fs.state}")
    print(f"Token util: {fs.token_util:.2f}")


def _cmd_checkpoint(args: argparse.Namespace) -> None:
    from maggy.mnemos.checkpoint import write_checkpoint
    from maggy.mnemos.db import MnemosDB

    d = _require_mnemos_dir()
    db = MnemosDB(d)
    cp = write_checkpoint(
        d, db, task_id="cli", fatigue=0.0, force=args.force,
    )
    print(f"Checkpoint written: {cp.id}")


def _cmd_resume(_args: argparse.Namespace) -> None:
    from maggy.mnemos.checkpoint import format_for_context, load_latest

    d = _require_mnemos_dir()
    cp = load_latest(d)
    if cp is None:
        print("No checkpoint found.")
        return
    print(format_for_context(cp))


def _cmd_handoff(_args: argparse.Namespace) -> None:
    from maggy.mnemos.db import MnemosDB
    from maggy.mnemos.handoff import build_handoff_node, format_handoff

    d = _require_mnemos_dir()
    db = MnemosDB(d)
    node = build_handoff_node(db, d, task_id="cli")
    print(format_handoff(node))
