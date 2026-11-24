"""Build the PR evidence record from the verify outcome (RFC §2.5; factory doc §5).

One row per approved criterion with a verdict kept distinct: failed (a check failed),
blocked (a check could not run, or no planned check ran), pending (a baseline, vision or
manual acceptance awaits a human), passed, or not applicable (a human recorded it). Only
artifacts that passed the secret scan are referenced, by path relative to the runner state
dir and sha256; withheld ones become verification gaps.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from maggy.runner.pr_evidence.models import ArtifactRef, CriterionRow, EvidenceRecord, RowVerdict
from maggy.runner.stages.spec_version import criterion_ids
from maggy.runner.verify.models import ViewResult
from maggy.runner.verify.run import VerifyOutcome

NOT_APPLICABLE = "recorded as not applicable by a human"


@dataclass(frozen=True)
class RecordInputs:
    ref: str
    spec_version: str
    outcome: VerifyOutcome
    criteria: list[str]
    scanned: tuple[list[Path], dict[Path, list[str]]]  # (referable, withheld -> findings)
    root: Path  # artifact paths are shown relative to it
    not_applicable: frozenset[str] = frozenset()


def build_record(inputs: RecordInputs) -> EvidenceRecord:
    rows = tuple(_row(inputs, cid) for cid in criterion_ids(inputs.criteria))
    waiting = tuple(f"[{row.criterion_id}] {row.verdict}: {row.detail}" for row in rows
                    if row.verdict in ("blocked", "pending"))
    failed = tuple(c.name for c in inputs.outcome.commands if not c.passed)
    return EvidenceRecord(inputs.ref, inputs.spec_version, inputs.outcome.sha, rows,
                          (*_withheld(inputs), *waiting), failed_commands=failed)


def _row(inputs: RecordInputs, cid: str) -> CriterionRow:
    results = [r for r in inputs.outcome.results if r.criterion_id == cid]
    entries = [e for e in inputs.outcome.entries if str(e.get("criterion_id")) == cid]
    kinds = tuple(dict.fromkeys(str(e.get("evidence", "")) for e in entries))
    if cid in inputs.not_applicable:
        return CriterionRow(cid, "not applicable", (), kinds, (), NOT_APPLICABLE)
    verdict, detail = _verdict(results, "manual" in kinds)
    checks = tuple(dict.fromkeys(_check_name(r) for r in results))
    return CriterionRow(cid, verdict, checks, kinds, _artifacts(inputs, results), detail)


def _verdict(results: list[ViewResult], manual: bool) -> tuple[RowVerdict, str]:
    for verdict, matches in (("failed", lambda r: r.verdict == "FAIL"),
                             ("blocked", lambda r: r.blocked),
                             ("pending", lambda r: r.verdict == "PENDING")):
        found = [r for r in results if matches(r)]
        if found:
            return verdict, found[0].reason
    if manual:
        return "pending", "manual acceptance: a human reviews it on the PR"
    if not results:
        return "blocked", "no planned check ran for this criterion"
    return "passed", "; ".join(dict.fromkeys(r.reason for r in results))


def _check_name(result: ViewResult) -> str:
    return f"{result.check} {result.viewport}".strip()


def _artifacts(inputs: RecordInputs, results: list[ViewResult]) -> tuple[ArtifactRef, ...]:
    allowed = set(inputs.scanned[0])
    return tuple(ArtifactRef(_relative(path, inputs.root), _digest(path),
                             f"{result.viewport} {kind}".strip())
                 for result in results for kind, path in result.artifacts.items()
                 if path in allowed)


def _withheld(inputs: RecordInputs) -> tuple[str, ...]:
    withheld = inputs.scanned[1]
    return tuple(f"[{r.criterion_id}] {r.check} {kind} withheld from the PR: secret scan "
                 f"({', '.join(withheld[path])})"
                 for r in inputs.outcome.results for kind, path in r.artifacts.items()
                 if path in withheld)


def _relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root)) if path.is_relative_to(root) else path.name


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
