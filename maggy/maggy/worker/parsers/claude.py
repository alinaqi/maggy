"""Parser for `claude -p --output-format json` (one result object)."""

from __future__ import annotations

from maggy.worker.parsers.base import (
    ParsedRun, as_dict, join_errors, load_object, number, pick_usage, text_or_none,
)

USAGE = {"input_tokens": "input_tokens", "output_tokens": "output_tokens",
         "cache_read_tokens": "cache_read_input_tokens",
         "cache_write_tokens": "cache_creation_input_tokens"}
BUDGET_SUBTYPE = "error_max_budget_usd"  # --max-budget-usd reached (recorded error.json)
MISSING = "claude-json: no result object in output (malformed or truncated)"


def _find_result(stdout: str) -> dict | None:
    """The whole stdout, else the last line that is a result object."""
    candidates = [stdout.strip(), *reversed(stdout.splitlines())]
    objects = (load_object(text) for text in candidates if text.strip())
    return next((o for o in objects if o and o.get("type") == "result"), None)


def _main_model(model_usage: object) -> str | None:
    usage = as_dict(model_usage)
    if not usage:
        return None
    return max(usage, key=lambda name: number(as_dict(usage[name]).get("costUSD")) or 0.0)


def _error(result: dict) -> str:
    errors = result.get("errors")
    messages = [str(e) for e in errors] if isinstance(errors, list) else []
    fallback = text_or_none(result.get("result")) or str(result.get("subtype", "error"))
    return join_errors(messages) or fallback


def parse_claude(stdout: str) -> ParsedRun:
    result = _find_result(stdout)
    if result is None:
        return ParsedRun(error=MISSING)
    failed = result.get("is_error") is True or str(result.get("subtype", "")).startswith("error")
    return ParsedRun(
        final_text="" if failed else (text_or_none(result.get("result")) or ""),
        cost_usd=number(result.get("total_cost_usd")),
        model=_main_model(result.get("modelUsage")),
        usage=pick_usage(result.get("usage"), USAGE),
        error=_error(result) if failed else None,
        session_ref=text_or_none(result.get("session_id")),
        budget_hit=result.get("subtype") == BUDGET_SUBTYPE,
    )
