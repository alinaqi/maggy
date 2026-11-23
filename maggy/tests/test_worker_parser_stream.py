"""Edge cases of the shared parser helpers: odd numbers, odd shapes, registry."""

from __future__ import annotations

import json
from typing import get_args

import pytest

from maggy.worker.adapter_spec import Parser
from maggy.worker.parsers import PARSERS, RawRun, parse_run
from maggy.worker.parsers.stream import run_stream


def test_registry_covers_every_adapter_parser_id():
    assert set(PARSERS) == set(get_args(Parser))


@pytest.mark.parametrize("value", ["Infinity", "NaN", "-Infinity"])
def test_non_finite_numbers_are_dropped_not_raised(value):
    stdout = ('{"type":"result","subtype":"success","is_error":false,"result":"done",'
              f'"total_cost_usd":{value},"usage":{{"input_tokens":{value}}}}}')
    parsed = parse_run("claude-json", RawRun(stdout=stdout), [])
    assert parsed.final_text == "done"
    assert parsed.cost_usd is None and parsed.usage == {}


def test_codex_odd_item_shape_and_unknown_event_do_not_raise():
    lines = [{"type": "turn.completed", "usage": {"input_tokens": 1}},
             {"type": "item.completed", "item": "not-a-dict"}]
    stdout = "\n".join(json.dumps(x) for x in lines) + '\n{"type":"x","n":Infinity}\n'
    parsed = parse_run("codex-jsonl", RawRun(stdout=stdout), [])
    assert parsed.error is None and parsed.usage == {"input_tokens": 1}


def test_handler_failure_is_reported_and_stream_continues():
    def boom(state, event):
        raise TypeError("bad shape")

    def finish(state, event):
        state.finished = True

    stdout = '{"type":"a"}\n{"type":"end"}\n'
    parsed = run_stream(stdout, {"a": boom, "end": finish}, "fake")
    assert "event 'a': unexpected shape" in parsed.error
