"""Output parsers turning raw CLI stdout/stderr into a ParsedRun (RFC §2.3).

Parsers never raise on bad input: malformed lines, truncated streams and
unexpected shapes are reported in `ParsedRun.error`.
"""

from __future__ import annotations

from collections.abc import Callable

from maggy.worker.parsers.base import ParsedRun, RawRun, quota_hit
from maggy.worker.parsers.claude import parse_claude
from maggy.worker.parsers.codex import parse_codex
from maggy.worker.parsers.opencode import parse_opencode
from maggy.worker.parsers.pi import parse_pi

__all__ = ["PARSERS", "ParsedRun", "RawRun", "parse_run"]

PARSERS: dict[str, Callable[[str], ParsedRun]] = {
    "claude-json": parse_claude,
    "codex-jsonl": parse_codex,
    "opencode-json": parse_opencode,
    "pi-jsonl": parse_pi,
    "text": lambda stdout: ParsedRun(final_text=stdout.strip()),
}


def _exit_error(raw: RawRun) -> str | None:
    if raw.exit_code in (0, None):
        return None
    tail = raw.stderr.strip()[-500:]
    return f"exit code {raw.exit_code}" + (f": {tail}" if tail else "")


def parse_run(parser: str, raw: RawRun, quota_patterns: list[str]) -> ParsedRun:
    """Parse one run; a non-zero exit with no parsed error still sets `error`."""
    parse = PARSERS.get(parser)
    if parse is None:
        raise ValueError(f"unknown parser {parser!r}; expected one of {sorted(PARSERS)}")
    parsed = parse(raw.stdout)
    error = parsed.error or _exit_error(raw)
    hit = quota_hit(quota_patterns, raw.stderr, error)
    return parsed.model_copy(update={"error": error, "quota_hit": hit})
