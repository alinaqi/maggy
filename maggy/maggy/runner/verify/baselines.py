"""Baseline approval (factory doc §5 "Approve new or changed visuals explicitly").

A missing baseline gets a PROPOSED image in the attempt dir, recorded as a
`baseline-proposed:<criterion>:<viewport>:<sha12>` annotation. A human approves it with a
`baseline-approved:<criterion>:<viewport>` DECISION carrying the image's sha256; only a
proposal whose file still hashes to that value is committed as the baseline.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from maggy.runner.awg_types import annotation_key
from maggy.runner.verify.models import ViewResult
from maggy.runner.verify.visual import baseline_path

PROPOSED, APPROVED = "baseline-proposed", "baseline-approved"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proposal(result: ViewResult) -> tuple[str, dict]:
    """The annotation (key, data) recording `result`'s proposed baseline."""
    path = result.artifacts["proposed"]
    digest = sha256(path)
    key = f"{PROPOSED}:{result.criterion_id}:{result.viewport}:{digest[:12]}"
    return key, {"criterion_id": result.criterion_id, "viewport": result.viewport,
                 "path": str(path), "sha256": digest}


def approval_command(ref: str, data: dict) -> str:
    key = f"{APPROVED}:{data['criterion_id']}:{data['viewport']}"
    return (f"awg decision {ref} --key {key} --title 'baseline approved' "
            f"--data '{{\"sha256\": \"{data['sha256']}\"}}'")


def approved_files(annotations: list[dict], decisions: list[dict]) -> dict[str, Path]:
    """Repo baseline path -> approved proposed image, for every intact approved proposal."""
    approved = {d["key"]: (d.get("data") or {}).get("sha256") for d in decisions
                if str(d.get("key", "")).startswith(f"{APPROVED}:")}
    found: dict[str, Path] = {}
    for note in annotations:
        data = note.get("data") or {}
        if not annotation_key(note).startswith(f"{PROPOSED}:"):
            continue
        key = f"{APPROVED}:{data.get('criterion_id')}:{data.get('viewport')}"
        if approved.get(key) == data.get("sha256") and _intact(data):
            found[str(baseline_path(data["criterion_id"], data["viewport"]))] = Path(data["path"])
    return found


def _intact(data: dict) -> bool:
    path = Path(str(data.get("path", "")))
    return path.is_file() and sha256(path) == data.get("sha256")
