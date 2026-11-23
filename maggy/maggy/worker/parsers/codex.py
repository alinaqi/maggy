"""Parser for `codex exec --json` (JSONL thread/turn/item events)."""

from __future__ import annotations

from maggy.worker.parsers.base import (
    ParsedRun, as_dict, load_object, pick_usage, text_or_none,
)
from maggy.worker.parsers.stream import StreamState, run_stream

USAGE = {"input_tokens": "input_tokens", "output_tokens": "output_tokens",
         "cache_read_tokens": "cached_input_tokens"}


def _message(raw: object) -> str:
    """Codex wraps API errors as a JSON string; surface the inner message."""
    text = str(raw or "unknown error")
    inner = as_dict(as_dict(load_object(text)).get("error"))
    if not text_or_none(inner.get("message")):
        return text
    status = as_dict(load_object(text)).get("status")
    return f"{inner['message']} (status {status})" if status else inner["message"]


def _thread(state: StreamState, event: dict) -> None:
    state.session_ref = text_or_none(event.get("thread_id"))


def _item(state: StreamState, event: dict) -> None:
    item = as_dict(event.get("item"))
    if item.get("type") == "agent_message":
        state.final_text = text_or_none(item.get("text")) or ""


def _completed(state: StreamState, event: dict) -> None:
    state.add_usage(pick_usage(event.get("usage"), USAGE))
    state.finished = True


def _failed(state: StreamState, event: dict) -> None:
    state.errors.append(_message(as_dict(event.get("error")).get("message")))
    state.finished = True


def _error(state: StreamState, event: dict) -> None:
    state.errors.append(_message(event.get("message")))


HANDLERS = {"thread.started": _thread, "item.completed": _item,
            "turn.completed": _completed, "turn.failed": _failed, "error": _error}


def parse_codex(stdout: str) -> ParsedRun:
    return run_stream(stdout, HANDLERS, "codex-jsonl")
