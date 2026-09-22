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
import re
import sys

_ID_RE = re.compile(r"^SA-[0-9]{3,}$")

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
    """A confirmed finding needs location, attack_scenario, and a finder AND a
    validator that are both named and distinct (an absent found_by must not let
    the finder!=validator rule pass silently)."""
    loc = f.get("location") or {}
    if not (loc.get("file") and loc.get("line")):
        errs.append(f"{fid}: confirmed but missing location file:line")
    if not f.get("attack_scenario"):
        errs.append(f"{fid}: confirmed but no attack_scenario")
    found, val = f.get("found_by"), f.get("validated_by")
    if not found:
        errs.append(f"{fid}: confirmed but no found_by (finder must be named)")
    if not val:
        errs.append(f"{fid}: confirmed but no validated_by (validator must be named)")
    if found and val and val == found:
        errs.append(f"{fid}: validated_by must differ from found_by ({found})")


def _check_schema(errs: list, fid: str, f: dict) -> None:
    """Enforce report-schema.json shape constraints (id pattern, title length,
    location types) so findings.json actually conforms, not just the enums."""
    if not _ID_RE.match(str(f.get("id", ""))):
        errs.append(f"{fid}: id must match SA-<digits> (e.g. SA-001)")
    title = f.get("title") or ""
    if isinstance(title, str) and 0 < len(title) < 8:
        errs.append(f"{fid}: title too short (min 8 chars)")
    loc = f.get("location")
    if loc is not None:
        line = loc.get("line") if isinstance(loc, dict) else None
        if not isinstance(loc, dict) or not loc.get("file"):
            errs.append(f"{fid}: location must be an object with a file")
        elif isinstance(line, bool) or not isinstance(line, int) or line < 1:
            errs.append(f"{fid}: location.line must be an integer >= 1")


def _check_finding(errs: list, seen: set, f: dict) -> None:
    fid = f.get("id", "<no-id>")
    for k in REQUIRED:
        if not f.get(k):
            errs.append(f"{fid}: missing required field {k!r}")
    if fid in seen:
        errs.append(f"{fid}: duplicate id")
    seen.add(fid)
    _check_schema(errs, fid, f)
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
