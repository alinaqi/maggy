"""Parser for `pi -p --mode json` (pi 0.73.1 AgentSessionEvent JSONL)."""

from __future__ import annotations

from maggy.worker.parsers.base import ParsedRun, as_dict, pick_usage, text_or_none
from maggy.worker.parsers.stream import StreamState, run_stream

USAGE = {"input_tokens": "input", "output_tokens": "output",
         "cache_read_tokens": "cacheRead", "cache_write_tokens": "cacheWrite"}
FAILED_STOPS = ("error", "aborted")


def _text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    parts = content if isinstance(content, list) else []
    return "".join(str(p.get("text", "")) for p in parts
                   if isinstance(p, dict) and p.get("type") == "text")


def _session(state: StreamState, event: dict) -> None:
    state.session_ref = text_or_none(event.get("id"))


def _message_end(state: StreamState, event: dict) -> None:
    message = as_dict(event.get("message"))
    if message.get("role") != "assistant":
        return
    usage = as_dict(message.get("usage"))
    state.model = text_or_none(message.get("model")) or state.model
    state.add_cost(as_dict(usage.get("cost")).get("total"))
    state.add_usage(pick_usage(usage, USAGE))
    state.final_text = _text_of(message.get("content"))
    stop = message.get("stopReason")
    if stop in FAILED_STOPS:
        state.errors.append(text_or_none(message.get("errorMessage")) or str(stop))


def _retry_end(state: StreamState, event: dict) -> None:
    if event.get("success") is False:
        state.errors.append(text_or_none(event.get("finalError")) or "retries exhausted")


def _agent_end(state: StreamState, event: dict) -> None:
    state.finished = True


HANDLERS = {"session": _session, "message_end": _message_end,
            "auto_retry_end": _retry_end, "agent_end": _agent_end}


def parse_pi(stdout: str) -> ParsedRun:
    return run_stream(stdout, HANDLERS, "pi-jsonl")
