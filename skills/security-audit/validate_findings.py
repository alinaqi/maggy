#!/usr/bin/env python3
"""Validate a security-audit findings.json against report-schema.json + the
audit-integrity rules that keep the process honest. Zero dependencies.

A `confirmed` finding must have a file:line location, an attack_scenario, and a
`validated_by` that differs from `found_by` (finder != validator). Ids unique,
enums valid. Exit 0 = clean; exit 1 = violations (printed to stderr).

Usage: validate_findings.py findings.json
"""
from __future__ import annotations

import json
import sys

CLASSES = {"injection", "authz", "authn", "secrets", "ssrf", "deserialization",
           "path-traversal", "memory-safety", "llm", "supply-chain", "cloud",
           "client-side", "dos", "data-isolation", "other"}
SEVERITIES = {"critical", "high", "medium", "low", "info"}
LIKELIHOODS = {"high", "medium", "low"}
VERDICTS = {"confirmed", "needs_validation", "rejected"}
REQUIRED = ("id", "title", "class", "severity", "likelihood", "verdict")


def _enum(errs: list, fid: str, field: str, val, allowed: set) -> None:
    if val not in allowed:
        errs.append(f"{fid}: {field}={val!r} not in {sorted(allowed)}")


def _check_confirmed(errs: list, fid: str, f: dict) -> None:
    """A confirmed finding needs location, attack_scenario, finder != validator."""
    loc = f.get("location") or {}
    if not (loc.get("file") and loc.get("line")):
        errs.append(f"{fid}: confirmed but missing location file:line")
    if not f.get("attack_scenario"):
        errs.append(f"{fid}: confirmed but no attack_scenario")
    found, val = f.get("found_by"), f.get("validated_by")
    if not val:
        errs.append(f"{fid}: confirmed but no validated_by (finder != validator)")
    elif found and val == found:
        errs.append(f"{fid}: validated_by must differ from found_by ({found})")


def _check_finding(errs: list, seen: set, f: dict) -> None:
    fid = f.get("id", "<no-id>")
    for k in REQUIRED:
        if not f.get(k):
            errs.append(f"{fid}: missing required field {k!r}")
    if fid in seen:
        errs.append(f"{fid}: duplicate id")
    seen.add(fid)
    _enum(errs, fid, "class", f.get("class"), CLASSES)
    _enum(errs, fid, "severity", f.get("severity"), SEVERITIES)
    _enum(errs, fid, "likelihood", f.get("likelihood"), LIKELIHOODS)
    _enum(errs, fid, "verdict", f.get("verdict"), VERDICTS)
    if f.get("verdict") == "confirmed":
        _check_confirmed(errs, fid, f)


def validate(doc: dict) -> list[str]:
    errs: list[str] = []
    if not isinstance(doc.get("audit"), dict) or not doc["audit"].get("target"):
        errs.append("audit.target is required")
    findings = doc.get("findings")
    if not isinstance(findings, list):
        return errs + ["findings must be a list"]
    seen: set = set()
    for f in findings:
        _check_finding(errs, seen, f)
    return errs


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    doc = json.load(open(argv[1]))
    errs = validate(doc)
    if errs:
        print(f"INVALID — {len(errs)} problem(s):", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    n = len(doc.get("findings", []))
    conf = sum(1 for f in doc["findings"] if f.get("verdict") == "confirmed")
    print(f"OK — {n} findings ({conf} confirmed), integrity checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
