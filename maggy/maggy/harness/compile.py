"""Compile one profile into a single plan across several agents.

Emitters may manage the same file (in project scope every agent uses the repo
AGENTS.md). Their managed regions are merged per path and planned once, so
apply never writes one file twice from stale plans. Each region records the
agents that emitted it, and files that harness.lock knows in this scope root
but no emitter manages any more are planned too, so their dropped regions are
removed. Whole-file copies (skills, extensions) come from each emitter's own plan.
"""

from __future__ import annotations

from pathlib import Path

from maggy.harness.changes import FileChange, HarnessContext, ManagedFile
from maggy.harness.emitters import (
    ClaudeEmitter, CodexEmitter, Emitter, EmitterSources, OpenCodeEmitter, PiEmitter, Scope,
)
from maggy.harness.fs_safe import real
from maggy.harness.lock import load_lock
from maggy.harness.plan import plan_files
from maggy.harness.schema import HarnessProfile

EMITTERS = {"claude": ClaudeEmitter, "codex": CodexEmitter, "opencode": OpenCodeEmitter, "pi": PiEmitter}
AGENTS = tuple(EMITTERS)


def emitters_for(agents: list[str], sources: EmitterSources) -> list[Emitter]:
    return [EMITTERS[name](sources) for name in agents]


def _merge(specs: dict[Path, ManagedFile], spec: ManagedFile, agent: str) -> None:
    spec = spec.model_copy(update={"owners": {rid: [agent] for rid in spec.regions}})
    have = specs.get(spec.path)
    if have is None:
        specs[spec.path] = spec
        return
    owners = {rid: sorted({*have.owners.get(rid, []), agent}) for rid in {**spec.regions, **have.regions}}
    specs[spec.path] = have.model_copy(update={
        "regions": {**spec.regions, **have.regions}, "owners": owners,
        "references_token": have.references_token or spec.references_token,
    })


def _orphans(ctx: HarnessContext, known: list[Path]) -> list[ManagedFile]:
    """Files in harness.lock for this root with regions this run may remove, not managed now."""
    root, run, seen = str(real(ctx.root)), set(ctx.agents or []), {str(real(p)) for p in known}
    out = []
    for path, entries in load_lock(ctx.lock_path).files.items():
        ours = [e for e in entries.values() if e.format and e.root == root and set(e.agents) <= run]
        if ours and path not in seen:
            out.append(ManagedFile(path=Path(path), format=ours[0].format, regions={}))
    return out


def _copies(emitter: Emitter, plan_for: tuple[HarnessProfile, Scope], own: set[Path]) -> list[FileChange]:
    return [change for change in emitter.plan(*plan_for) if change.path not in own]


def compile_plan(profile: HarnessProfile, scope: Scope, emitters: list[Emitter]) -> list[FileChange]:
    """Merged managed files planned once, then each emitter's whole-file copies."""
    specs: dict[Path, ManagedFile] = {}
    copies: dict[Path, FileChange] = {}
    for emitter in emitters:
        files = emitter.managed_files(profile, scope)
        for spec in files:
            _merge(specs, spec, emitter.agent)
        for change in _copies(emitter, (profile, scope), {spec.path for spec in files}):
            copies.setdefault(change.path, change)
    ctx = scope.context().model_copy(update={"agents": [e.agent for e in emitters]})
    managed = list(specs.values()) + _orphans(ctx, list(specs))
    return plan_files(managed, ctx) + list(copies.values())
