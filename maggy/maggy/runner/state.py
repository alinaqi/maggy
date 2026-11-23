"""The leases this runner holds, on disk, so a restarted runner can reconcile (RFC §2.4).

`<state_dir>/runner/state.json` (path injectable) maps each held ref to its claim and, once
the worker has finished and its checks ran, the WorkerResult. Writes are atomic (temp file +
rename), so a kill -9 mid-write leaves the previous version, never a torn file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from maggy.runner.awg_types import Claim
from maggy.runner.config import RunnerConfig
from maggy.worker.models import WorkerResult

Held = tuple[Claim, WorkerResult | None]


class RunnerState:
    def __init__(self, path: Path) -> None:
        self.path = path

    def held(self) -> list[Held]:
        entries = self._load().values()
        return [(Claim.model_validate(e["claim"]),
                 WorkerResult.model_validate(e["result"]) if e.get("result") else None)
                for e in entries]

    def hold(self, claim: Claim) -> None:
        self._change(claim.ref, {"claim": claim.model_dump(mode="json"), "result": None})

    def record(self, ref: str, result: WorkerResult) -> None:
        entry = self._load().get(ref)
        if entry is not None:
            self._change(ref, {**entry, "result": result.model_dump(mode="json")})

    def drop(self, ref: str) -> None:
        self._change(ref, None)

    def _change(self, ref: str, entry: dict | None) -> None:
        held = self._load()
        if entry is None:
            held.pop(ref, None)
        else:
            held[ref] = entry
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"held": held}, indent=2))
        os.replace(tmp, self.path)

    def _load(self) -> dict:
        try:
            return dict(json.loads(self.path.read_text()).get("held") or {})
        except (OSError, ValueError, AttributeError):
            return {}


def state_for(config: RunnerConfig) -> RunnerState:
    return RunnerState(config.state_file or config.state_dir / "runner" / "state.json")


def latest_handoff(shown: dict) -> str:
    """The newest `[handoff <attempt>] ...` comment on the item, or ""."""
    bodies = [str(c.get("body", "")) for c in shown.get("comments") or []]
    notes = [body for body in bodies if body.startswith("[handoff ")]
    return notes[-1] if notes else ""
