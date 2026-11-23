"""Contract tests: every parser over every recorded/synthetic CLI fixture."""

from __future__ import annotations

import pytest

from worker_fixture_helpers import all_cases, run_case

CASES = all_cases()
IDS = [f"{cli}-{case}" for cli, case in CASES]
each_case = pytest.mark.parametrize(("cli", "case"), CASES, ids=IDS)


@each_case
def test_final_text(cli, case):
    parsed, expect = run_case(cli, case)
    assert parsed.final_text == expect["final_text"]


@each_case
def test_cost(cli, case):
    parsed, expect = run_case(cli, case)
    if expect["cost_usd"] is None:
        assert parsed.cost_usd is None
    else:
        assert parsed.cost_usd == pytest.approx(expect["cost_usd"])


@each_case
def test_model(cli, case):
    parsed, expect = run_case(cli, case)
    assert parsed.model == expect["model"]


@each_case
def test_error(cli, case):
    parsed, expect = run_case(cli, case)
    if expect["error"] is None:
        assert parsed.error is None
    else:
        assert expect["error"] in (parsed.error or "")


@each_case
def test_quota_hit(cli, case):
    parsed, expect = run_case(cli, case)
    assert parsed.quota_hit is expect["quota_hit"]


@each_case
def test_session_ref(cli, case):
    parsed, expect = run_case(cli, case)
    assert parsed.session_ref == expect["session_ref"]


@each_case
def test_usage(cli, case):
    parsed, expect = run_case(cli, case)
    for key, value in expect.get("usage", {}).items():
        assert parsed.usage[key] == value
