"""Node management CLI commands for Mnemos."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from maggy.mnemos.constants import MNEMOS_DIR


def register_node_commands(sub: argparse._SubParsersAction) -> None:
    """Register 'add' and 'nodes' subcommands."""
    p_add = sub.add_parser("add", help="Add a node")
    p_add.add_argument(
        "node_type",
        choices=["goal", "constraint", "fact", "decision"],
    )
    p_add.add_argument("content")

    p_nodes = sub.add_parser("nodes", help="List nodes")
    p_nodes.add_argument("--type", dest="node_type_filter")


def cmd_add(args: argparse.Namespace) -> None:
    """Create a node from CLI."""
    from maggy.mnemos.db import MnemosDB
    from maggy.mnemos.models import MnemoNode

    d = _require_dir()
    db = MnemosDB(d)
    type_map = {
        "goal": "GoalNode",
        "constraint": "ConstraintNode",
        "fact": "FactNode",
        "decision": "DecisionNode",
    }
    node = MnemoNode(
        type=type_map[args.node_type],
        task_id="cli",
        content=args.content,
    )
    db.insert_node(node)
    print(f"Created {node.type}: {node.id}")


def cmd_list_nodes(args: argparse.Namespace) -> None:
    """List nodes, optionally filtered by --type."""
    from maggy.mnemos.db import MnemosDB

    d = _require_dir()
    db = MnemosDB(d)
    nodes = db.list_nodes(node_type=args.node_type_filter)
    if not nodes:
        print("No nodes found.")
        return
    fmt = "{:<14} {:<16} {:<10} {}"
    print(fmt.format("ID", "Type", "Status", "Content"))
    print("-" * 70)
    for n in nodes:
        print(fmt.format(
            n.id, n.type, n.status, n.content[:40],
        ))


def _require_dir() -> Path:
    cwd = Path.cwd()
    d = cwd / MNEMOS_DIR
    if not d.is_dir():
        print("Error: .mnemos/ not found.", file=sys.stderr)
        sys.exit(1)
    return d
