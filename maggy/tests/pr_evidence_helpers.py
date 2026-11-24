"""A mixed-verdict verify outcome for the PR evidence record (factory doc §5): AC1 passed,
AC2 failed (its log leaks a token), AC3 blocked (no browser), AC4 pending (no vision
backend), AC5 not applicable (a human said so)."""

from __future__ import annotations

from pathlib import Path

from maggy.review.models import Finding, Severity
from maggy.runner.pr_evidence.build import RecordInputs
from maggy.runner.verify.models import ViewResult
from maggy.runner.verify.run import VerifyOutcome

SHA = "0123456789abcdef0123456789abcdef01234567"
LEAK = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
CRITERIA = [f"[AC{n}] criterion {n}" for n in range(1, 6)]
ENTRIES = [{"criterion_id": "AC1", "evidence": "unit"},
           {"criterion_id": "AC2", "evidence": "e2e"},
           {"criterion_id": "AC3", "evidence": "visual"},
           {"criterion_id": "AC4", "evidence": "visual"},
           {"criterion_id": "AC5", "evidence": "manual"}]
BLOCKING = Finding(file="calc.py", line=3, severity=Severity.blocking,
                   title="discount applied twice", detail="apply() runs the rule again")


def _file(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def mixed_outcome(root: Path) -> VerifyOutcome:
    ok = _file(root, "attempts/A1/verify/functional/AC1/run.log", "ok\n")
    leaky = _file(root, "attempts/A1/verify/functional/AC2/run.log", f"token {LEAK}\n")
    results = [ViewResult("AC1", "", "PASS", "test_ac1 passed", {"log": ok}, "functional"),
               ViewResult("AC2", "", "FAIL", "test_ac2: failed: assert 100 == 90",
                          {"log": leaky}, "functional"),
               ViewResult("AC3", "mobile", "PENDING", "chromium is not available",
                          blocked=True),
               ViewResult("AC4", "desktop", "PENDING", "no vision backend available",
                          check="vision")]
    return VerifyOutcome(SHA, [], results, ENTRIES)


def mixed_inputs(root: Path) -> RecordInputs:
    outcome = mixed_outcome(root)
    leaky = root / "attempts/A1/verify/functional/AC2/run.log"
    allowed = [p for r in outcome.results for p in r.artifacts.values() if p != leaky]
    return RecordInputs(ref="AWG-42", spec_version="7", outcome=outcome, criteria=CRITERIA,
                        scanned=(allowed, {leaky: ["github token"]}), root=root,
                        not_applicable=frozenset({"AC5"}))
