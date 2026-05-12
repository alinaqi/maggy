"""TDD verification — runs pytest/ruff/coverage between executor steps."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120
COVERAGE_THRESHOLD = 80.0


@dataclass
class VerifyResult:
    """Outcome of a verification step."""

    passed: bool
    detail: str
    tests_found: int = 0
    tests_failed: int = 0


async def verify_tests_exist(wd: str) -> VerifyResult:
    """Run pytest --collect-only to verify tests were written."""
    code, output = await _run_cmd(
        ["python3", "-m", "pytest", "--collect-only", "-q"], wd,
    )
    count = _count_collected(output)
    if code != 0 or count == 0:
        return VerifyResult(False, output[:500], count)
    return VerifyResult(True, f"{count} tests collected", count)


async def verify_tests_fail(wd: str) -> VerifyResult:
    """Run pytest -x and confirm failures (RED phase)."""
    code, output = await _run_cmd(
        ["python3", "-m", "pytest", "-x", "--tb=short", "-q"], wd,
    )
    failed = _count_failures(output)
    if code == 0:
        return VerifyResult(
            False, "Tests passed — expected failures (RED)",
        )
    if failed == 0:
        return VerifyResult(False, f"Non-test error:\n{output[:500]}")
    return VerifyResult(True, f"{failed} tests failed (RED)", 0, failed)


async def verify_tests_pass(wd: str) -> VerifyResult:
    """Run pytest -x and confirm all pass (GREEN phase)."""
    code, output = await _run_cmd(
        ["python3", "-m", "pytest", "-x", "--tb=short", "-q"], wd,
    )
    if code != 0:
        return VerifyResult(
            False, f"Tests failing:\n{output[:500]}",
        )
    return VerifyResult(True, "All tests pass (GREEN)")


async def verify_lint(wd: str) -> VerifyResult:
    """Run ruff check on the working directory."""
    code, output = await _run_cmd(
        ["python3", "-m", "ruff", "check", "."], wd,
    )
    if code != 0:
        return VerifyResult(False, f"Lint errors:\n{output[:500]}")
    return VerifyResult(True, "Lint clean")


async def verify_coverage(
    wd: str, threshold: float = COVERAGE_THRESHOLD,
) -> VerifyResult:
    """Run pytest with coverage and check threshold."""
    code, output = await _run_cmd(
        ["python3", "-m", "pytest", "--cov", "-q"], wd,
    )
    pct = _parse_coverage(output)
    if pct < threshold:
        return VerifyResult(
            False, f"Coverage {pct:.0f}% < {threshold:.0f}%",
        )
    return VerifyResult(True, f"Coverage {pct:.0f}%")


async def _run_cmd(
    cmd: list[str], cwd: str,
) -> tuple[int, str]:
    """Run a subprocess, return (exit_code, output)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
        stdout, _ = await asyncio.wait_for(
            proc.communicate(), timeout=DEFAULT_TIMEOUT,
        )
        text = (stdout or b"").decode("utf-8", errors="replace")
        return proc.returncode or 0, text
    except asyncio.TimeoutError:
        return 1, "Command timed out"
    except FileNotFoundError:
        return 1, f"Command not found: {cmd[0]}"


def _count_collected(output: str) -> int:
    """Parse 'N tests collected' from pytest output."""
    m = re.search(r"(\d+)\s+tests?\s+collected", output)
    return int(m.group(1)) if m else 0


def _count_failures(output: str) -> int:
    """Parse 'N failed' from pytest summary."""
    m = re.search(r"(\d+)\s+failed", output)
    return int(m.group(1)) if m else 0


def _parse_coverage(output: str) -> float:
    """Parse 'TOTAL ... NN%' from coverage output."""
    m = re.search(r"TOTAL\s+.*?(\d+)%", output)
    return float(m.group(1)) if m else 0.0
