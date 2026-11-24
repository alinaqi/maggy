"""The argv (never a shell) that runs ONE named test with a junit report, per runner."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from maggy.harness.schema_sections import Regression
from maggy.runner.regression.invocation import invocation

JUNIT = Path("/tmp/out/junit.xml")


def test_pytest_by_name_and_by_node_id() -> None:
    config = Regression(runner="pytest", command="py -m pytest")
    argv, env = invocation(config, "test_add", JUNIT)
    assert argv == ["py", "-m", "pytest", "-k", "test_add", "-p", "no:cacheprovider",
                    f"--junitxml={JUNIT}"] and env == {}
    argv, _ = invocation(config, "tests/test_calc.py::test_add", JUNIT)
    assert argv[3] == "tests/test_calc.py::test_add"


def test_pytest_default_command() -> None:
    argv, _ = invocation(Regression(), "test_add", JUNIT)
    assert argv[:3] == ["python", "-m", "pytest"]


def test_node_test_reports_junit() -> None:
    argv, _ = invocation(Regression(runner="node-test"), "adds", JUNIT)
    assert argv == ["node", "--test", "--test-reporter=junit",
                    f"--test-reporter-destination={JUNIT}", "--test-name-pattern", "adds"]


def test_playwright_junit_via_env() -> None:
    argv, env = invocation(Regression(runner="playwright"), "coupon rejects", JUNIT)
    assert argv == ["npx", "playwright", "test", "--reporter=junit", "-g", "coupon rejects"]
    assert env == {"PLAYWRIGHT_JUNIT_OUTPUT_NAME": str(JUNIT)}


def test_command_fills_placeholders_per_token() -> None:
    config = Regression(runner="command", command="make test NAME={test} OUT={junit}")
    argv, _ = invocation(config, "a b; rm -rf /", JUNIT)
    assert argv == ["make", "test", "NAME=a b; rm -rf /", f"OUT={JUNIT}"]


def test_command_runner_needs_a_command() -> None:
    with pytest.raises(ValidationError):
        Regression(runner="command")


def test_pytest_runs_resolved_node_ids_not_a_tree_wide_k() -> None:
    ids = ("tests/test_a.py::test_ac1", "tests/test_c.py::TestX::test_ac1")
    argv, _ = invocation(Regression(runner="pytest", command="py -m pytest"), ids, JUNIT)
    assert argv == ["py", "-m", "pytest", *ids, "-p", "no:cacheprovider",
                    f"--junitxml={JUNIT}"]
