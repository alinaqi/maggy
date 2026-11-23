"""Parser for `opencode run --format json` (step/text/tool/error events)."""

from __future__ import annotations

from maggy.worker.parsers.base import ParsedRun, as_dict, pick_usage, text_or_none
from maggy.worker.parsers.stream import StreamState, run_stream

TOKENS = {"input_tokens": "input", "output_tokens": "output"}
CACHE = {"cache_read_tokens": "read", "cache_write_tokens": "write"}


def _step_start(state: StreamState, event: dict) -> None:
    state.session_ref = text_or_none(event.get("sessionID")) or state.session_ref
    state.final_text = ""
    state.finished = False


def _text(state: StreamState, event: dict) -> None:
    text = text_or_none(as_dict(event.get("part")).get("text")) or ""
    state.final_text = "\n".join(t for t in (state.final_text, text) if t)


def _step_finish(state: StreamState, event: dict) -> None:
    part = as_dict(event.get("part"))
    tokens = as_dict(part.get("tokens"))
    state.add_cost(part.get("cost"))
    state.add_usage(pick_usage(tokens, TOKENS) | pick_usage(tokens.get("cache"), CACHE))
    state.finished = part.get("reason") not in (None, "tool-calls")


def _error(state: StreamState, event: dict) -> None:
    error = as_dict(event.get("error"))
    message = text_or_none(as_dict(error.get("data")).get("message"))
    state.errors.append(message or text_or_none(error.get("name")) or "unknown error")
    state.session_ref = text_or_none(event.get("sessionID")) or state.session_ref
    state.finished = True


HANDLERS = {"step_start": _step_start, "text": _text,
            "step_finish": _step_finish, "error": _error}


def parse_opencode(stdout: str) -> ParsedRun:
    return run_stream(stdout, HANDLERS, "opencode-json")
