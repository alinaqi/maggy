"""Targeted output filtering for the council reviewer — strip low-signal bytes
before a per-file diff slice is re-sent to a 2–5 model panel (the ×panel
multiplier is where the real token waste is).

The hard invariant: **a changed line (`+`/`-`) or a hunk header (`@@`) is NEVER
dropped.** Only runs of *unchanged context lines* far from a change collapse to a
marker, and known generated/lockfiles are stubbed. The full patch is always one
`get_diff(path)` tool call away, so this is lossless for the reviewer's purpose.
This is the build-not-buy answer to RTK: format-specific, unit-testable, no
third-party binary in the command path.
"""

from __future__ import annotations

# Lockfiles / generated artifacts: noise to a *semantic* reviewer; the static
# gate covers their correctness. Diff body is stubbed, not sent.
_GENERATED_NAMES = (
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "cargo.lock", "go.sum", "composer.lock", "gemfile.lock", "uv.lock",
)
_GENERATED_MARKERS = (
    "/dist/", "/build/", "/.next/", "/node_modules/", "/vendor/",
    ".min.js", ".min.css", ".map", ".snap",
)


def is_generated(path: str) -> bool:
    """True for lockfiles / build output / snapshots — diff body is low-signal."""
    p = path.lower()
    if any(p.endswith(name) for name in _GENERATED_NAMES):
        return True
    return any(marker in p for marker in _GENERATED_MARKERS)


def compress_patch(patch: str, context: int = 3) -> str:
    """Collapse runs of unchanged context lines, keeping `context` around each
    change. Every non-context line (``@@``/``+``/``-``/``\\``) is preserved."""
    lines = patch.splitlines()
    n = len(lines)
    if n == 0:
        return patch
    # A context line is one starting with a single space; everything else is an
    # anchor (hunk header, added, removed, no-newline marker) and is always kept.
    keep = [not ln.startswith(" ") for ln in lines]
    for i in range(n):
        if not lines[i].startswith(" "):
            for j in range(max(0, i - context), min(n, i + context + 1)):
                if lines[j].startswith(" "):
                    keep[j] = True
    out: list[str] = []
    i = 0
    while i < n:
        if keep[i]:
            out.append(lines[i])
            i += 1
            continue
        j = i
        while j < n and not keep[j]:
            j += 1
        hidden = j - i
        out.append(f"… {hidden} unchanged line{'s' if hidden != 1 else ''} hidden …")
        i = j
    return "\n".join(out)
