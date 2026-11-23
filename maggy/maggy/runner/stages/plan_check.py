"""Plan checks (RFC §2.5 gate): unique keys, known deps, an acyclic DAG, every criterion
covered by the test plan, and every planned file inside the repository."""

from __future__ import annotations

from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from maggy.runner.stages.plan_models import Plan


def plan_problems(plan: Plan, criteria: list[str], repo: Path) -> list[str]:
    return [*_key_problems(plan), *_cycle(plan), *_coverage(plan, criteria),
            *_files(plan, repo)]


def _key_problems(plan: Plan) -> list[str]:
    keys = [t.key for t in plan.tasks]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    unknown = sorted({d for t in plan.tasks for d in t.depends_on if d not in keys})
    return ([f"duplicate task keys: {', '.join(dupes)}"] if dupes else []) + (
        [f"depends_on names unknown task keys: {', '.join(unknown)}"] if unknown else [])


def _cycle(plan: Plan) -> list[str]:
    graph = {t.key: set(t.depends_on) for t in plan.tasks}
    try:
        TopologicalSorter(graph).prepare()
    except CycleError as exc:
        return [f"task dependencies form a cycle: {' -> '.join(map(str, exc.args[1]))}"]
    return []


def _coverage(plan: Plan, criteria: list[str]) -> list[str]:
    keys = {t.key for t in plan.tasks}
    covered = {e.criterion_id for e in plan.test_plan}
    missing = [c for c in criteria if c not in covered]
    unknown = sorted(covered - set(criteria))
    orphans = sorted({e.task for e in plan.test_plan if e.task not in keys})
    return ([f"criteria without a test_plan entry: {', '.join(missing)}"] if missing else []) + (
        [f"test_plan names unknown criteria: {', '.join(unknown)}"] if unknown else []) + (
        [f"test_plan names unknown tasks: {', '.join(orphans)}"] if orphans else [])


def _files(plan: Plan, repo: Path) -> list[str]:
    root = repo.resolve()
    outside = sorted({f for t in plan.tasks for f in t.files if not _inside(f, root)})
    return [f"files outside the repository: {', '.join(outside)}"] if outside else []


def _inside(path: str, root: Path) -> bool:
    if not path or Path(path).is_absolute():
        return False
    return (root / path).resolve().is_relative_to(root)
