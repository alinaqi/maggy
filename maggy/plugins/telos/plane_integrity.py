"""Plane 3 — Integrity: structural intent checks → F3.

Checks:
  IF-3  Orphan symbols (no reason edges)
  IF-4  Empty contracts (no pre/post/invariants)
  IF-6  Stale reasons (proposed > N days)
  IF-7  Scope sprawl (reason scopes > 10 files)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_here = Path(__file__).resolve().parent


def _ensure_models():
    if "telos_models" not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            "telos_models", _here / "models.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["telos_models"] = mod
        spec.loader.exec_module(mod)


_ensure_models()

_SPRAWL_THRESHOLD = 10


def compute_f3(
    reasons: list,
    orphans: list[dict[str, Any]],
    stale: list,
) -> dict[str, Any]:
    violations: list[str] = []
    total_checks = 0

    for o in orphans:
        violations.append(f"IF-3 orphan: {o['name']}")
    total_checks += max(len(orphans), 1)

    for r in reasons:
        total_checks += 1
        if not r.has_contracts:
            violations.append(
                f"IF-4 empty contract: {r.id}"
            )

    for s in stale:
        total_checks += 1
        violations.append(f"IF-6 stale: {s.id}")

    for r in reasons:
        if len(r.scope) > _SPRAWL_THRESHOLD:
            total_checks += 1
            violations.append(
                f"IF-7 sprawl: {r.id} ({len(r.scope)} files)"
            )

    f3 = 1.0 - len(violations) / max(total_checks, 1)
    return {
        "f3": max(f3, 0.0),
        "violations": violations,
    }
