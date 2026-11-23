"""Event-stream driver shared by the JSONL parsers (codex, opencode, pi)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from maggy.worker.parsers.base import ParsedRun, join_errors, json_lines, number


@dataclass
class StreamState:
    final_text: str = ""
    cost_usd: float | None = None
    model: str | None = None
    usage: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    session_ref: str | None = None
    finished: bool = False

    def add_cost(self, value: object) -> None:
        amount = number(value)
        if amount is not None:
            self.cost_usd = (self.cost_usd or 0.0) + amount

    def add_usage(self, counts: dict[str, int]) -> None:
        for key, value in counts.items():
            self.usage[key] = self.usage.get(key, 0) + value

    def result(self, problems: list[str]) -> ParsedRun:
        return ParsedRun(final_text=self.final_text, cost_usd=self.cost_usd,
                         model=self.model, usage=self.usage,
                         error=join_errors(self.errors + problems),
                         session_ref=self.session_ref)


Handler = Callable[[StreamState, dict], None]


def _apply(state: StreamState, event: dict, handlers: dict[str, Handler]) -> str | None:
    handler = handlers.get(str(event.get("type")))
    try:
        if handler:
            handler(state, event)
    except (TypeError, ValueError, AttributeError) as exc:
        return f"event {event.get('type')!r}: unexpected shape ({exc})"
    return None


def run_stream(text: str, handlers: dict[str, Handler], name: str) -> ParsedRun:
    """Feed every known event to its handler; unknown event types are ignored."""
    events, problems = json_lines(text)
    state = StreamState()
    for event in events:
        problem = _apply(state, event, handlers)
        problems += [problem] if problem else []
    if not state.finished:
        problems.append(f"{name}: stream ended before completion (truncated)")
    return state.result(problems)
