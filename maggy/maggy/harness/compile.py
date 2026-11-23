"""Compile one profile into a single plan across several agents.

Emitters may manage the same file (in project scope every agent uses the repo
AGENTS.md). Their managed regions are merged per path and planned once, so
apply never writes one file twice from stale plans. Whole-file copies
(skills, extensions) come from each emitter's own plan.
"""

from __future__ import annotations

from pathlib import Path

from maggy.harness.changes import FileChange, ManagedFile
from maggy.harness.emitters import (
    ClaudeEmitter, CodexEmitter, Emitter, EmitterSources, OpenCodeEmitter, PiEmitter, Scope,
)
from maggy.harness.plan import plan_files
from maggy.harness.schema import HarnessProfile

EMITTERS = {"claude": ClaudeEmitter, "codex": CodexEmitter, "opencode": OpenCodeEmitter, "pi": PiEmitter}
AGENTS = tuple(EMITTERS)


def emitters_for(agents: list[str], sources: EmitterSources) -> list[Emitter]:
    return [EMITTERS[name](sources) for name in agents]


def _merge(specs: dict[Path, ManagedFile], spec: ManagedFile) -> None:
    have = specs.get(spec.path)
    if have is None:
        specs[spec.path] = spec
        return
    specs[spec.path] = have.model_copy(update={
        "regions": {**spec.regions, **have.regions},
        "references_token": have.references_token or spec.references_token,
    })


def _copies(emitter: Emitter, plan_for: tuple[HarnessProfile, Scope], own: set[Path]) -> list[FileChange]:
    return [change for change in emitter.plan(*plan_for) if change.path not in own]


def compile_plan(profile: HarnessProfile, scope: Scope, emitters: list[Emitter]) -> list[FileChange]:
    """Merged managed files planned once, then each emitter's whole-file copies."""
    specs: dict[Path, ManagedFile] = {}
    copies: dict[Path, FileChange] = {}
    for emitter in emitters:
        files = emitter.managed_files(profile, scope)
        for spec in files:
            _merge(specs, spec)
        for change in _copies(emitter, (profile, scope), {spec.path for spec in files}):
            copies.setdefault(change.path, change)
    return plan_files(list(specs.values()), scope.context()) + list(copies.values())
