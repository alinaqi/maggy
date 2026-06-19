"""Deterministic static gate — the part the LLM council structurally can't do.

The council reads diffs; it never COMPILES. So an out-of-scope variable (runtime
ReferenceError), a type error, or a syntax error sails straight through. This runs
the real compiler/linter on the PR's code and turns its output into findings.

Ground truth: these findings skip the refute pass (you can't "refute" tsc) and are
filtered to the PR's CHANGED files so we report regressions, not pre-existing debt.
"""
from __future__ import annotations

import asyncio
import re
import subprocess
from pathlib import Path

from .models import Finding, Severity

# tsc:  path(line,col): error TS1234: message
_TS = re.compile(r"^(?P<file>[^()\n]+?)\((?P<line>\d+),\d+\): error (?P<code>TS\d+): (?P<msg>.+)$")
# ruff concise:  path:line:col: CODE message
_RUFF = re.compile(r"^(?P<file>[^:\n]+):(?P<line>\d+):\d+: (?P<code>[A-Z]+\d+) (?P<msg>.+)$")

# ruff rules that are real bugs (the Python analogue of the zennyEnabled crash),
# not style. F821 = undefined name; E9 = syntax; F82x = undefined export/__all__.
_RUFF_SELECT = "E9,F821,F822,F823,F811,F406,F501,F502,F522,F601,F602,F631,F701,F702"


def _run(cmd, cwd, timeout=600):
    try:
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "") + "\n" + (r.stderr or "")
    except Exception as e:  # noqa: BLE001
        return f"__TOOL_ERROR__ {type(e).__name__}: {e}"


def _norm(p: str) -> str:
    p = p.strip().replace("\\", "/").lstrip("./")
    while p.startswith("../"):
        p = p[3:]
    return p


def _match_changed(err_path: str, changed: set[str]) -> str | None:
    """tsc/ruff paths can be project-relative (../../libs/...); match by path suffix
    against the PR's changed files so we only report errors the PR is responsible for."""
    e = _norm(err_path)
    for c in changed:
        if c == e or c.endswith("/" + e) or e.endswith("/" + c) or e.endswith(c):
            return c
    return None


def _finding(file, line, code, msg, tool):
    return Finding(
        file=file,
        line=int(line) if line else None,
        severity=Severity.blocking,
        title=f"{tool}: {code} — {msg[:90]}",
        detail=f"Deterministic {tool} error on a changed line: {code} {msg}. "
               f"This is a compiler/linter error (not an opinion) and will break the build "
               f"or crash at runtime — it must be fixed before merge.",
        evidence=f"static analysis ({tool})",
    )


def _ts_gate(lp: Path, changed_ts: set[str], on_log) -> list[Finding]:
    files_arg = ",".join(sorted(changed_ts))
    proj = _run(["npx", "nx", "show", "projects", "--affected", "--files=" + files_arg], lp, 120)
    projects = [p.strip() for p in proj.splitlines()
                if p.strip() and not p.strip().endswith("-e2e") and "__TOOL_ERROR__" not in p]
    if not projects:
        on_log("[static] ts: no affected nx projects resolved; skipping typecheck")
        return []
    on_log(f"[static] ts: typecheck {projects}")
    out = _run(["npx", "nx", "run-many", "-t", "typecheck", "-p", *projects, "--skip-nx-cache"], lp, 600)
    if out.startswith("__TOOL_ERROR__"):
        on_log(f"[static] ts: typecheck did not run ({out[:80]})")
        return []
    found, seen = [], set()
    for ln in out.splitlines():
        m = _TS.match(ln.strip())
        if not m:
            continue
        # TS5xxx/TS6xxx are nx/tsconfig PROJECT-CONFIG errors (e.g. TS6307 "file not
        # listed in project"), not code bugs — skip them. Real code errors are TS1xxx
        # (syntax) and TS2xxx/TS7xxx/TS18xxx (type/undefined-name).
        if m.group("code").startswith(("TS5", "TS6")):
            continue
        cf = _match_changed(m.group("file"), changed_ts)
        if not cf:
            continue  # error in a file this PR didn't change -> pre-existing, not ours
        key = (cf, m.group("line"), m.group("code"))
        if key in seen:
            continue
        seen.add(key)
        found.append(_finding(cf, m.group("line"), m.group("code"), m.group("msg"), "tsc"))
    return found


def _py_gate(lp: Path, changed_py: set[str], on_log) -> list[Finding]:
    # changed_py are PR-controlled filenames; drop any leading-dash path so it
    # can't be smuggled to ruff as a flag, and terminate options with `--`.
    existing = [c for c in sorted(changed_py) if (lp / c).exists() and not c.startswith("-")]
    if not existing:
        return []
    on_log(f"[static] py: ruff (bug rules) on {len(existing)} changed file(s)")
    out = _run(["ruff", "check", "--select", _RUFF_SELECT, "--output-format", "concise",
                "--no-cache", "--", *existing], lp, 180)
    if out.startswith("__TOOL_ERROR__"):
        on_log(f"[static] py: ruff did not run ({out[:80]})")
        return []
    found, seen = [], set()
    for ln in out.splitlines():
        m = _RUFF.match(ln.strip())
        if not m:
            continue
        cf = _match_changed(m.group("file"), changed_py) or _norm(m.group("file"))
        key = (cf, m.group("line"), m.group("code"))
        if key in seen:
            continue
        seen.add(key)
        found.append(_finding(cf, m.group("line"), m.group("code"), m.group("msg"), "ruff"))
    return found


async def run_static_gate(deps, langs, on_log) -> list[Finding]:
    """Run the deterministic compiler/linter gate against the local checkout.
    Returns blocking findings for errors on the PR's changed files (empty if no
    local checkout, tooling missing, or nothing to check)."""
    lp = deps.local_path
    if not lp:
        on_log("[static] skipped — no local checkout (--repo-path)")
        return []
    lp = Path(lp)
    changed = {f["filename"] for f in deps.files}
    # caveat if the local tree isn't exactly the PR head (best-effort, still useful)
    head = _run(["git", "rev-parse", "HEAD"], lp, 20).strip().splitlines()[0:1]
    if head and head[0] and head[0] != deps.head_sha:
        on_log(f"[static] note: local HEAD {head[0][:8]} != PR head {deps.head_sha[:8]} "
               "— gate runs against the local checkout")

    def _work():
        out: list[Finding] = []
        ts = {c for c in changed if c.endswith((".ts", ".tsx"))}
        py = {c for c in changed if c.endswith(".py")}
        if "typescript" in langs and ts:
            out += _ts_gate(lp, ts, on_log)
        if "python" in langs and py:
            out += _py_gate(lp, py, on_log)
        return out

    findings = await asyncio.to_thread(_work)
    on_log(f"[static] {len(findings)} deterministic error(s) on changed files")
    return findings
