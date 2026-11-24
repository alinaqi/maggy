"""The argv (never a shell) and extra env that run ONE named test with a junit report.

The test name is always its own argv token (or substituted inside one token for
`runner: command`), so a name from the plan can never inject a shell command.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from maggy.harness.schema_sections import Regression

Invocation = tuple[list[str], dict[str, str]]
DEFAULTS = {"pytest": "python -m pytest", "node-test": "node --test",
            "playwright": "npx playwright test"}


def invocation(config: Regression, test: str, junit: Path) -> Invocation:
    if config.runner == "command":
        return _command(config.command or "", test, junit), {}
    base = shlex.split(config.command or DEFAULTS[config.runner])
    if config.runner == "pytest":
        return [*base, *_pytest_selector(test), "-p", "no:cacheprovider",
                f"--junitxml={junit}"], {}
    if config.runner == "node-test":
        return [*base, "--test-reporter=junit", f"--test-reporter-destination={junit}",
                "--test-name-pattern", test], {}
    return [*base, "--reporter=junit", "-g", test], {"PLAYWRIGHT_JUNIT_OUTPUT_NAME": str(junit)}


def _pytest_selector(test: str) -> list[str]:
    """A node id or file path runs as given; a bare test name is selected with -k."""
    return [test] if "::" in test or test.endswith(".py") else ["-k", test]


def _command(line: str, test: str, junit: Path) -> list[str]:
    return [token.replace("{test}", test).replace("{junit}", str(junit))
            for token in shlex.split(line)]
