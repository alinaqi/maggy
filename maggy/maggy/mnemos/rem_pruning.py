"""REM Phase 3: Task Graph Pruning."""

from __future__ import annotations

from maggy.mnemos.db import MnemosDB
from maggy.mnemos.db_queries import bulk_update_status


def find_completed_tasks(db: MnemosDB) -> list[str]:
    """Find task_ids where all GoalNodes are done."""
    goals = db.list_nodes(node_type="GoalNode")
    task_goals: dict[str, list[str]] = {}
    for g in goals:
        task_goals.setdefault(g.task_id, []).append(g.status)
    return [
        tid for tid, statuses in task_goals.items()
        if all(s != "ACTIVE" for s in statuses)
    ]


def crystallize_task(db: MnemosDB, task_id: str) -> int:
    """Mark all nodes for task_id as CRYSTALLIZED."""
    nodes = db.list_nodes(task_id=task_id)
    ids = [
        n.id for n in nodes
        if n.status not in ("CRYSTALLIZED", "EVICTED")
    ]
    return bulk_update_status(db.conn, ids, "CRYSTALLIZED")


def run_task_pruning(db: MnemosDB) -> dict:
    """Execute Phase 3."""
    completed = find_completed_tasks(db)
    total = 0
    for tid in completed:
        total += crystallize_task(db, tid)
    return {
        "crystallized_tasks": len(completed),
        "nodes_crystallized": total,
    }
