"""Parsers never raise: malformed, truncated, unknown and empty input."""

from __future__ import annotations

import json

import pytest

from maggy.worker.parsers import ParsedRun, RawRun, parse_run
from worker_fixture_helpers import load_meta, raw_run

STRUCTURED = {"claude": "claude-json", "codex": "codex-jsonl",
              "opencode": "opencode-json", "pi": "pi-jsonl"}
STREAMS = ["codex", "opencode", "pi"]
GARBAGE = ["", "not json at all {", "[1, 2, 3]", "42\n", '{"type": "result"', "\x00\xff"]


def _parse(cli: str, stdout: str, exit_code: int = 0) -> ParsedRun:
    return parse_run(STRUCTURED[cli], RawRun(stdout=stdout, exit_code=exit_code), [])


@pytest.mark.parametrize("cli", STRUCTURED)
@pytest.mark.parametrize("stdout", GARBAGE)
def test_garbage_never_raises_and_sets_error(cli, stdout):
    parsed = _parse(cli, stdout)
    assert parsed.error
    assert parsed.final_text == ""


@pytest.mark.parametrize("cli", STRUCTURED)
def test_truncated_success_output_reports_error(cli):
    stdout = raw_run(cli, "success").stdout
    parsed = _parse(cli, stdout[: len(stdout) * 2 // 3])
    assert parsed.error


@pytest.mark.parametrize("cli", STREAMS)
def test_stream_cut_at_line_boundary_reports_truncation(cli):
    lines = raw_run(cli, "success").stdout.splitlines()
    parsed = _parse(cli, "\n".join(lines[:-1]) + "\n")
    assert "truncated" in parsed.error


@pytest.mark.parametrize("cli", STREAMS)
def test_unknown_events_are_ignored(cli):
    lines = raw_run(cli, "success").stdout.splitlines()
    extra = json.dumps({"type": "future.event", "payload": {"x": 1}})
    parsed = _parse(cli, "\n".join([lines[0], extra, *lines[1:]]))
    assert parsed.error is None
    assert parsed.final_text == "done"


@pytest.mark.parametrize("cli", STREAMS)
def test_malformed_line_is_reported_but_rest_is_parsed(cli):
    lines = raw_run(cli, "success").stdout.splitlines()
    parsed = _parse(cli, "\n".join([lines[0], "{oops", *lines[1:]]))
    assert "line 2" in parsed.error
    assert parsed.final_text == "done"


@pytest.mark.parametrize("cli", STRUCTURED)
def test_nonzero_exit_without_parsed_error_sets_error(cli):
    parsed = _parse(cli, raw_run(cli, "success").stdout, exit_code=3)
    assert "exit code 3" in parsed.error


def test_quota_hit_scans_stderr_and_error_but_not_final_text():
    raw = RawRun(stdout="ok", stderr="HTTP 503: Rate Limit reached", exit_code=1)
    assert parse_run("text", raw, ["rate limit"]).quota_hit is True
    assert parse_run("text", raw, ["usage limit"]).quota_hit is False
    chatty = RawRun(stdout="discussing the rate limit design", exit_code=0)
    assert parse_run("text", chatty, ["rate limit"]).quota_hit is False


def test_unknown_parser_id_is_rejected():
    with pytest.raises(ValueError, match="unknown parser"):
        parse_run("yaml-stream", RawRun(stdout=""), [])


def test_claude_parser_takes_result_line_after_noise():
    body = (raw_run("claude", "success").stdout).strip()
    parsed = _parse("claude", "warning: something\n" + body + "\n")
    assert parsed.final_text == "done"
    assert parsed.error is None
